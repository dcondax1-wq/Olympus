---
title: Kalshi edge, team K6 (Fed, Treasury yields, SOFR vs official rates data): NO EDGE PROVEN
family: kalshi
date: 2026-11-19
status: rejected - no edge proven (Fed vs bill-implied, Treasury yields vs official par yields + vol model, daily SOFR); no candidate file written
---

# Kalshi K6: can official rates data price Kalshi's rates markets better than the crowd? No (not proven)

Research only. Kalshi's PUBLIC market data (GET, no key, at most 1 request a second, never an order) and free official
data: Treasury par / constant-maturity yields, T-bill yields, the Fed target range, EFFR, SOFR and Freddie Mac PMMS, all
from FRED's public csv download (the Treasury yields there are Treasury's own daily par curve: checked against 6,728
Kalshi settlement values, 0 mismatches). Nothing armed, no key used, the live bot untouched.

## Owner summary

| Idea | Held-out result (fees in) | Trades a month | $/month at $10 a bet | Verdict |
|---|---|---|---|---|
| Fed decision markets vs the 1-month T-bill (free stand-in for fed funds futures) | win 7%, **-80% per $1** (n 43, 15 meetings) | 2 | about -$16 | Loses. The market is 13x more accurate than the bill model |
| Fed: always sell the long shot (buy NO when YES is 10c or less, last 10 days) | win 100%, +3.0% per $1 (n 30); older half -1.9% | 1.4 | about +$0.40 | Too small and too few to matter |
| Treasury yield markets (10Y weekly, 2Y/5Y/10Y/30Y weekly closes, "how high / how low") vs the official close + a volatility model | win 61%, **+27.5% per $1, range -3% to +62%** (n 389, 80 events) | 41 | about +$113, **not proven** | Not proven: range includes zero; the same series as the older half LOSES (-21%); the best pocket failed its replication (-26%) |
| Daily SOFR markets vs the NY Fed's own SOFR history | win 33%, -68% per $1 (n 3; older half -63%, n 26) | 3 | loses | Loses. The market knows the day's repo trading, we do not |
| Weekly / monthly S&P 500 and Nasdaq-100 close markets | Kalshi has **no settled weekly or monthly close markets** (only 2 "S&P monthly max" events) | - | - | Cannot be tested |

**Verdict: nothing to send live.** No `research/lab/kalshi_candidates/K6.json` was written, on purpose. The only
positive number (+27.5% on Treasury yields) does not clear the red team's verifier (`research/kalshi_red_team/verify.py`:
WEAK, t 1.67 under the multiple-testing bar 3.02, range includes zero) and it falls apart where it should be strongest:
on the 2025-26 weekly 10Y markets (the same kind of market the rule was fitted on) it loses 21%.

## What earlier teams already covered (not redone)

| Team | Covered |
|---|---|
| A | Calibration / base rates: crypto 15-min and hourly, S&P / Nasdaq hourly above-below; favourite-longshot cells |
| B | Crypto structure: ladder consistency, lognormal vol model, time of day, late favourites, maker fills; the bot's bad bet kinds |
| C | Weather vs archived NWS MOS; S&P / Nasdaq DAILY ranges with an ES / NQ realised-vol model; gas, FX, Rotten Tomatoes; econ releases (Fed favourite 24 h out, 8 events, descriptive only) |
| K1 | Nasdaq / S&P hourly above-below with a futures fair-value model; weather locks and after-1-pm model; market making on hourly index markets |
| K3 | Arbitrage (range buckets, ladders, live scan, CPI m/m vs y/y); CPI / payrolls / U3 / claims with the Cleveland Fed nowcast; late resolution on METAR weather |
| K4 | Polymarket copy (crypto, sports); sports favourite-longshot; crypto coin x hour slices; Fed / CPI not tested (too few events) |
| K5 | Slow public-number markets (gas, TSA, YouTube, Truth Social, App Store, Spotify); liquidity rewards |
| 2026-11-04 | The old live bot: it lost to the fee (0.07 x C x P x (1-P), rounded up per order) |

New here: Fed meetings vs official short rates, Treasury yield markets (terminal and barrier) vs the official par
curve, daily SOFR vs official SOFR, and the weekly / monthly index question.

## Rules used everywhere

- Taker buys at the ask (NO = 1 - yes bid); fee 0.07 x C x P x (1-P) rounded up to the cent on a $10 order
  (C = floor(10 / P)). Profit per $1 = net / (cost + fee). One trade per market (the first time the rule fires).
- Every model probability uses only data published before the quote: the decision quote is the hourly bid/ask that ends
  20:00-23:00 ET, and the official yield for that day is assumed public at 18:30 ET (Treasury posts its curve by about
  6 pm). EFFR (published the next morning) is used with a one-day lag. `info_ts` < order time on every row (checked by
  the red-team verifier).
- Strikes were picked with the last official yield published BEFORE the market opened, never with the settlement
  value, so the sample is not conditioned on the outcome. Barrier events whose window had not ended by the harvest
  (2026-11-18) were dropped: only their already-hit strikes are settled, which would bias the sample toward YES.
- Older half / newer half by settlement date: model parameters, the trading margin and the spread cap were fixed on the
  older half, the newer half was read once. 95% ranges are cluster bootstraps, one cluster = one event (all strikes of
  one week / meeting / day move together). About 70 trading cells were scored in all.

## 1. Fed decisions (KXFED 2021-26, KXFEDDECISION 2023-26; 33 meetings with quotes)

CME fed funds / SOFR futures history is not free (CME DataMine and FedWatch history are paid), so the stand-in is the
1-month T-bill: if the meeting is k days away, the bill's average rate = today's rate + change x (30 - k) / 30. The
bill-minus-EFFR spread is the median of the previous 120 business days that had no meeting in the next month. Older half =
meetings before 2025 (18), newer half = 2025-26 (15).

| | Older half | Newer half (held out) |
|---|---|---|
| Brier, Kalshi mid price | **0.043** | **0.006** |
| Brier, bill model | 0.240 | 0.080 |
| Rule fixed on the older half (model 20c+ better than the price, spread 3c or less) | n 38, win 11%, -64% per $1 | n 43, win 7%, -80% per $1 (range -100% to -47%) |

The bill is far too noisy for this job: in the 2023 debt-ceiling and bank-stress months it "implied" a 1.4-point cut
(April) and a 2.5-point hike (May); bill supply swings move it by more than a 25 bp decision. In October 2026 it "implied" a 26 bp hike that never came. Kalshi
prices Fed meetings very well (Brier 0.006 in 2025-26); this is the most efficient market in the study.

## 2. Treasury yield markets (3,070 markets with quotes, 2023-02 to 2026-11; +180 for the replication)

Series: KXTNOTEW (10Y weekly ladder, 2023-02 to 2026-06), KXUST2A / 5A / 10A / 30A (2Y-30Y weekly "above X", Jul-Nov
2026), and the "how high / how low" barrier markets (KX10YRDIRHW/LW/HM/LM, KX2YRDIRHM/LM, KX5YRDIRHM, KX30YRDIRHM; Sep-Nov
2026). All settle on Treasury's daily par yield (FRED DGS2 / 5 / 10 / 30, exact match).

Model: the next daily changes are Student-t, scaled by an exponentially weighted average of past official daily
changes; an FOMC day in the horizon gets extra variance; barrier markets use 6,000 simulated daily paths. Fitted on the
older half by log loss (best: half-life 90 days, 4 degrees of freedom, 0.9 x the measured volatility, FOMC variance
x2.5). The trading rule picked on the older half: buy when the model beats the price plus fee by 2c, spread 6c or less.

| | n | Events | Win | Net per $1 (95%) | Trades / month | $/month at $10 |
|---|---|---|---|---|---|---|
| Older half (2023-24 weekly 10Y) | 112 | 40 | 25% | +58% (+10% to +111%) | 6 | +$33 |
| **Newer half, all** | **389** | **80** | **61%** | **+27.5% (-3% to +58%)** | **41** | **+$113** |
| - weekly 10Y 2025-26 (same series as the older half) | 37 | 17 | 46% | **-21%** (-56% to +21%) | 7 | -$16 |
| - 2Y / 5Y / 10Y / 30Y weekly closes (Jul-Nov 2026) | 274 | 54 | 58% | +19% (-16% to +64%) | 69 | +$133 |
| - "how high / how low" barriers (Sep-Nov 2026) | 78 | 9 | 82% | +80% (+44% to +114%) | 49 | +$393 (9 events) |
| Barrier rule FROZEN on 4 barrier series not looked at before (5Y / 30Y / 7Y) | 21 | 4 | 24% | **-26%** (-87% to +108%) | 13 | -$35 |
| Control: same model side, no margin | 911 | 101 | 38% | -20% | 90 | -$178 |

Brier on the newer half: market 0.07698, model 0.07694 (a tie). By series the newer half swings from -25% (10Y) to +97%
(2Y), and within the older half a 4c margin gave +0.6% while a 2c margin gave +58%: the pattern of noise, not of a
model that knows better (a real edge grows with the margin). The barrier pocket (+80%) rests on 9 events in two months,
several of them the same yield move seen through 2Y, 10Y and 30Y at once, and it did not replicate.

Red-team verifier on the held-out trade list (`trades_yields_test.json`, 40 rules tried): **WEAK** (net +27.5%, range
-2.9% to +62.4%, halves +13% / +42%, t 1.67 vs bar 3.02). On the barrier replication: FALSE.

Variant (width only, model centred on the market's own median): the ladders are too thin in 2023-24 to fit it on the
older half (57 usable quotes), so it was not used.

## 3. Daily SOFR (KXSOFRD, Aug-Nov 2026, 54 days)

Each market settles on SOFR for the business day before its date (published 8:00 ET) and trades through that day, while
the newest official print is a day older. Model: yesterday's SOFR plus the history of 1-day changes for the same kind of
day (month-end, month-start, mid-month settlement, other), all from 2019 on. Brier: market 0.047 / 0.002 (older / newer
half), model 0.061 / 0.013. Trading the disagreements lost 63% (n 26) and 68% (n 3). The crowd sees the repo market of
the day itself; the official history cannot.

## 4. Weekly / monthly index and mortgage markets

Kalshi's weekly and monthly S&P 500 / Nasdaq-100 close series (KXINXW, KXINXWD, KXNASDAQ100W, KXINXM, KXNASDAQ100M and
their old names) have no settled markets at all; only "S&P 500 max monthly" has 2 events (May-June 2026). Nothing to
test. The weekly mortgage-rate series (KXFRM, Freddie Mac PMMS) ended in February 2024, so it could not be traded today
and was not studied.

## Honest limits

- Hourly candle bid / ask are quotes, not fills; the book depth is unknown. Only 14% of the held-out Treasury trades had
  any traded volume in their quote hour: these books are thin and a $10 order may not fill at the shown ask.
- The 18:30 ET publication time is an assumption (Treasury usually posts earlier); quotes start at 20:00 ET for margin.
- The weekly 10Y markets are listed under `/historical`, one request per market; 1,230 of 1,516 chosen markets had quotes.
- Fed: 33 meetings is a small sample for any rule; the bill is a weak stand-in for futures. A free official archive of
  fed funds futures settlements would be needed to test the original idea properly.

## What would change the answer

1. A real futures feed for the Fed idea (ZQ / SR3 daily settlements), e.g. from the PC's NinjaTrader, logged forward.
2. Forward paper logging of the Treasury barrier markets (how high / how low): only ~2 complete months exist; 12+ months
   with order-book depth would settle whether the crowd misprices touch probabilities.

## Files and reruns (`research/kalshi_edge_K6/`)

| File | What |
|---|---|
| `kk6.py` | Polite GET-only client (1 request / s, cache in /home/user/kalshi_cache/knew1), fee and P&L per $1 |
| `survey.py` | Which rates / index series exist, how many settled markets, rules -> `data/survey.json` |
| `fred.py` | Official daily series from FRED -> `data/fred.json` |
| `harvest.py` | Settled markets + hourly bid/ask (strikes chosen before the open) -> `data/q_<series>.jsonl.gz` |
| `yields.py` | Treasury study -> `results_yields.json`, `trades_yields_test.json` (verifier format); `K6_CENTER=1` = width-only variant |
| `replicate_barrier.py` | Frozen barrier rule on 4 unseen series -> `results_barrier_replication.json` |
| `fed.py` | Fed study -> `results_fed.json` |
| `sofr.py` | Daily SOFR study -> `results_sofr.json`, `trades_sofr_test.json` |

```
python research/kalshi_edge_K6/fred.py
python research/kalshi_edge_K6/harvest.py KXTNOTEW --near 0.12 --days 8      # and the other series, see the docstrings
python research/kalshi_edge_K6/yields.py && python research/kalshi_edge_K6/replicate_barrier.py
python research/kalshi_edge_K6/fed.py && python research/kalshi_edge_K6/sofr.py
python research/kalshi_red_team/verify.py research/kalshi_edge_K6/trades_yields_test.json --rules-tried 40
```

## Tested and rejected (add to the list)

Fed decisions vs bill-implied probabilities; Fed long-shot NO; Treasury yield markets (weekly 10Y ladder, 2Y-30Y weekly
closes, how high / how low) vs official par yields + Student-t volatility model; daily SOFR vs official SOFR history.
