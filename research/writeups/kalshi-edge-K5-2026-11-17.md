---
title: Kalshi edge, team K5 (answer partly public before close, slow niche markets, liquidity rewards)
family: kalshi
date: 2026-11-17
status: no tradeable taker edge; one weak paper candidate (about $3/month); rewards are the only real lead and need a real-order test
---

# Kalshi K5 (2026-11-17): slow "public number" markets and paid rewards

## Owner summary

| Idea | Test result (newest part, fees in) | $/month at $10 a bet | Verdict |
|---|---|---|---|
| Buy the late favourite (80-98.5c) when the answer is mostly public (YouTube views, Truth Social counts, TSA week, App Store #1) | +4.4% per $1 (range +2.2% to +6.0%), 1 loss in 110 | about **+$3** | Weak. The older half was -1.3%, so paper only |
| Same idea, only the safest 95-98.5c bets (gas week, TSA, YouTube) | +2% to +3%, almost no losses | about +$1 to +$2 | Not proven: one loss erases 30 wins |
| Forecast AAA gas from yesterday's price | -45% (daily), -75% (weekly) | loses | Market is far better |
| Back yesterday's #1 Spotify song | -24% (range -39% to -8%) | loses | Market already knows |
| Buy everything (control) | -18% to -78% | loses | The spread + fee cost |
| **Rewards: keep resting orders (about $185) on Rotten Tomatoes / shipping-strait weekly markets** | rewards about $6-13 a day per market vs fills losing 3-10% | **maybe +$150 to +$470 for 3 markets** (an estimate, not measured) | **The only real lead.** It needs real orders, so only the owner can test it. The program ends Jan 1, 2027 |

**Verdict:** there is no taker edge worth money. Kalshi stays paused. I wrote one weak paper rule
(`research/lab/kalshi_live_candidate.json`, about $3 a month). Nothing is armed. The rewards program is the first idea in five
teams with a plausible positive number. It can only be checked by resting real orders, which is the owner's call.

## Rules used everywhere
- Kalshi PUBLIC data only (GET, no key, no account, no order): series list, settled markets (live + `/historical`),
  hourly candles, the public trade tape, order books, and the public `/incentive_programs` list. Nothing armed.
- Taker buys at the ask (NO = 1 - yes bid). Fee 0.07 x C x p x (1-p), rounded up to the cent on a $10 order. Spread over 6c skipped.
  Maker fills are charged the maker fee 0.0175 x p x (1-p) everywhere (conservative).
- I fixed a time split per series before looking at any outcome and read the test half once. Two splits were moved
  before that read, for data coverage only: gas to 2026-09-01, because daily AAA values start 2026-03; Truth Social to
  2026-10-01 / 10-25, because older candles had too few two-sided quotes. Ranges are 95% cluster bootstraps (one
  cluster = one event). A cell is carried forward only if its training t beats a one-sided Bonferroni bar over every
  training cell (79 cells, bar t 3.22). Eight "known answer" cells were written down before the run and are reported
  whatever their training result.
- **Cells counted:** 79 training cells + 8 pre-registered + 1 pooled family (taker), and 11 series x 2 halves (rewards):
  **about 110 in all.**

## 1. Scan: slow markets settled on a free, scheduled public number

16,485 series were scanned (`data/raw/series_all.json`, gitignored). The ones whose answer is public, or can be nowcast, before trading closes:

| Series | Settles on | Is part of the answer public before close? | Volume (contracts) | Tested |
|---|---|---|---|---|
| KXAAAGASD / W / M (US gas) | AAA daily average | Yes: yesterday's AAA value. Daily changes are smooth (AR(1) 0.77, sd 1.7c) | 54M / 63M / 63M | yes |
| KXTSAW (TSA weekly average) | TSA daily numbers | Yes: on Sunday, Monday-Saturday are published | 6.4M | yes |
| KXYTVIEWSW (max daily YouTube views in a week) | YouTube Charts | Yes: the week ends about 38 h before close | 8.6M | yes |
| KXTRUTHSOCIAL weekly / daily (Trump post counts) | Roll Call count | Weekly: the week ends about 10 h before close. Daily: the posts are live | 8.1M / 0.6M | yes |
| KXAPPRANKFREE (#1 free iPhone app at 10 am) | Apple chart | Yes: the live chart is public | 3.9M | yes |
| KXSPOTIFYD (#1 US Spotify song) | Spotify daily chart | Yesterday's chart only | 21.8M | yes |
| KXNETFLIXRANKSHOW | Netflix weekly top 10 | FlixPatrol dailies (no free history) | 18M | control only |
| Mentions (KXTRUMPMENTION etc., 1.3B) | transcripts | Only during the live event | huge | rewards only: no timestamped transcripts for history |
| Weather 1-min ASOS late in the day | NWS | Done by K1/K3: the price moves before the reading is public | | not redone |
| KXRT (Rotten Tomatoes) | RT score | The live score is public, but there is no free score history | 96M | rewards only |

TSA's own site blocks automated downloads, so TSA was tested on Kalshi's prices only (no TSA nowcast).

## 2. Taker results (test half; train in brackets)

| Idea | n train / test | Edge per $1, test (95%) | Train | Bets/month | $/month at $10 | Max losing streak |
|---|---|---|---|---|---|---|
| **Pooled "answer public" late favourite, 80-98.5c** (5 pre-registered cells) | 165 / 110 | **+4.4% (+2.2 to +6.0)**; exact worst case (1 loss, loss-rate bound 4.2% vs 4.9% break-even) **+1.0%** | -1.3% (-5.1 to +2.3) | 7.3 | **+$3.20** | 1 |
| - YouTube views, 12 h before close | 31 / 13 | +3.5% (+2.3 to +5.1) | +2.8% | 14 | | 0 |
| - Truth Social week, 5 h before close | 6 / 7 | +9.4% (+5.9 to +13.9) | +2.3% | 7 | | 0 |
| - Truth Social day, 1 h before close | 3 / 15 | +4.6% (+3.0 to +6.8) | -31% (n 3) | 17 | | 0 |
| - TSA week, Sunday 4 pm ET | 92 / 64 | +4.2% (+0.7 to +6.8) | -1.3% (-6.6 to +4.1) | 6 | | 1 |
| - App Store #1, 1 h before | 33 / 11 | +3.0% (+2.5 to +3.6) | -3.1% | 4 | | 0 |
| 95-98.5c favourites (9 carried cells: gas week, TSA, YouTube, Spotify) | 30-59 / 10-42 each | +2.3% to +3.2% (YouTube 24 h -0.8%, Spotify -2.6%) | +2.1% to +3.2% | 3-9 each | +$1 to +$2 | 1 |
| AAA gas nowcast (model says 5c+ cheap), daily | 544 / 275 | -44.5% (-70 to -11) | -55% | 100 | -$445 | 28 |
| AAA gas nowcast, weekly | 64 / 33 | -75% (-100 to -56) | -67% | 13 | -$98 | 15 |
| Spotify: back yesterday's #1 | 103 / 49 | -23.6% (-38.8 to -8.0) | -18.1% | 7 | -$17 | 2 |
| Control: buy every quote, per series | | -18% (gas day) to -78% (YouTube) | | | | |

Why the 95-98.5c cells are not trusted: they are built from almost no losses. With 0 losses in 12-42 bets, the exact 95% bound on the
loss rate is 7-26%, against a break-even of about 3%. The bootstrap range looks tight only because it never saw a loss.

Why the pooled cell is only a paper rule: the same five cells were slightly negative in the older half. A sign flip between halves
is what K4 saw on sports favourites. The test half's range does clear zero, even with the exact bound. The money is tiny:
7 bets a month, about $3 a month at $10.

## 3. Liquidity rewards (public terms, measured cost)

**Terms** (help.kalshi.com "Liquidity Incentive Program"; public API `/incentive_programs`, period_reward in centi-cents):
- The book is snapshotted every second.
- Your orders score size x DiscountFactor^(ticks behind the reference price). The reference price is where depth reaches
  Target/5. Target is 100-20,000 contracts, and the discount factor is 0.5 on the markets here.
- You are paid your share of the period's pool. Snapshots where either side is under Target pay nobody.
- Paid daily from about 6 am ET. US users only. The program **ends Jan 1, 2027**, and Kalshi can change it at any time.
- Right now: 5,722 active programs, about **$106,000 a day**, typically $100 a day per strike on the weekly markets.
- Pools grew about 10x in September 2026 (for example Rotten Tomatoes: $12k in July, $650k in October).

**Do makers as a group earn more from the pool than they lose on fills?** For each settled market since 2026-09-01 (up to 200
per series), I took the full public trade tape. The maker side of each trade is scored at settlement, then the market's
reward pool is added. Train = closes before 2026-10-15, test = after.

| Series | Markets (test) | Fills only, test | Fills + pool, test (95%) | Fills + pool, train |
|---|---|---|---|---|
| KXRT (Rotten Tomatoes) | 134 | -2.7% | **+3.0% (+1.0 to +5.4)** | +3.0% (-0.5 to +6.1) |
| KXPANAMAWEEKLY | 37 | -5.1% | **+6.7% (+4.9 to +8.7)** | +14.5% |
| KXBABELMANDEBWEEKLY | 45 | -6.1% | **+6.3% (+2.0 to +12.6)** | +20.5% |
| KXTEMPMIAH (Miami hourly temp) | 73 | -0.8% | **+5.6% (+0.5 to +11.5)** | +7.7% |
| KXSUEZWEEKLY | 32 | -7.2% | +2.2% (-9.5 to +14.7) | +47.6% |
| KXAAAGASD | 49 | +0.9% | +1.3% (-0.9 to +4.3) | +1.4% |
| KXTRUMPMENTION | 77 | +0.8% | +1.1% (-2.4 to +4.1) | +1.1% |
| KXHORMUZWEEKLY | 39 | -10.1% | -1.2% (-7.6 to +2.9) | +2.4% |
| KXTRUTHSOCIAL | 55 | -8.1% | **-4.2% (-9.1 to -1.4)** | +1.0% |
| KXYTVIEWSW | 75 | -25.9% | -6.2% (-27 to +15) | +36.9% |

Without rewards, fills lose 3-10% per $1 on most series. That matches K1's -10% to -14% on index hourlies. With the pool
added, four series stay positive in the test half. The pool numbers are an upper bound, because they assume every
snapshot pays.

**One new order** (Target/5 = 200 contracts a side at the reference price, about $185 locked). Eight order-book snapshots over
30 minutes, every snapshot valid. Fills assumed to come in at the same share as the reward:

| Series | My share | Reward $/day | Fills $/day | Net $/day | Net if fills are 2x | Per $1 a day |
|---|---|---|---|---|---|---|
| Babel-el-Mandeb weekly | 12.6% | 12.6 | 99 | **+6.5** | +0.5 | +3.7% |
| Rotten Tomatoes | 7.4% | 7.4 | 75 | **+5.4** | +3.4 | +2.8% |
| Panama weekly | 5.8% | 5.8 | 47 | **+3.5** | +1.1 | +1.9% |
| Suez weekly | 6.0% | 6.0 | 62 | +1.5 | -3.0 | +0.8% |
| Hormuz weekly | 9.2% | 9.2 | 98 | -0.7 | -10.6 | -0.4% |
| Truth Social weekly | 12.9% | 12.9 | 256 | -8.0 | -28.8 | -4.1% |

Read this as a lead, not a result:
1. The fill model is an assumption. An order resting behind the best price is filled mostly on big moves, so its fills are likely worse than the makers' average.
2. The share comes from 30 minutes on one afternoon. Depth changes overnight, and others add depth as pools grow.
3. It needs real resting orders, so it cannot be paper-tested from public data, and `tools/kalshi_paper.py` has no maker mode.
4. The program ends in 6 weeks.

If the owner ever wants to test it: one market, the smallest size, one week, and compare the reward credits against the
fills. Only he can place those orders.

## Files and reruns (`research/kalshi_edge_K5/`, raw cache and data/raw gitignored)

| File | What |
|---|---|
| `harvest.py`, `harvest_all.sh` | settled markets + hourly candles (public, cached, resumable; about 1 h) |
| `study.py` | taker study (splits, cells, Bonferroni bar, pre-registered cells, controls) -> `results.json` |
| `pooled.py` | pooled pre-registered family + exact binomial bounds -> `results_pooled.json` |
| `rewards_scan.py`, `rewards_repeat.py` | active reward programs + order-book shares -> `data/rewards_snapshot.json`, `data/rewards_repeat.json` |
| `maker_fills.py`, `rewards_report.py` | public trade tape, makers' P&L with and without the pool -> `results_rewards_sep.json`, `results_rewards_order.json` |
| `lib.py`, `net.py` | copied from K4 (fee, bootstrap, polite GET client) |

```
bash research/kalshi_edge_K5/harvest_all.sh
python research/kalshi_edge_K5/study.py && python research/kalshi_edge_K5/pooled.py
python research/kalshi_edge_K5/maker_fills.py KXRT,KXPANAMAWEEKLY,... 200 2026-09-01 _sep
python research/kalshi_edge_K5/rewards_repeat.py KXRT,KXPANAMAWEEKLY,... 8 240
python research/kalshi_edge_K5/rewards_report.py _sep 2026-10-15
```
