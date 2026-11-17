---
title: Kalshi liquidity rewards, the paper rule replayed on the last 30 days of the public tape
family: kalshi
date: 2026-11-17
status: no proven edge (pooled net is not positive in both halves); two weekly shipping series positive in both halves on estimated depth; paper only
---

# Kalshi rewards backtest (2026-11-17): rewards minus fill losses, last 30 days

## Owner table (net $ a day per $100 parked; first 15 days / last 15 days)

| Series | Base rule | If others' depth is 2x (half the reward) | With the 5c pause | Verdict |
|---|---|---|---|---|
| Panama weekly (KXPANAMAWEEKLY) | **+$1.13 / +$1.40** | +$0.22 / +$0.53 | +$2.15 / +$1.67 | positive in both halves |
| Bab-el-Mandeb weekly (KXBABELMANDEBWEEKLY) | **+$1.89 / +$0.75** | +$0.96 / +$0.20 | +$2.08 / +$1.42 | positive in both halves |
| Rotten Tomatoes (KXRT) | +$0.61 / **-$1.15** | +$0.34 / -$1.27 | +$1.13 / -$0.22 | loses in the newer half |
| Art auctions (KXART) | n/a / +$1.83 | n/a / +$1.11 | n/a / +$1.98 | only 15 days of programs |
| YouTube weekly views (KXYTVIEWSW) | -$0.54 / +$2.62 | -$0.60 / +$2.54 | -$0.59 / +$2.24 | the fills decide it (70 fills), rewards tiny |
| Weekly executive orders (KXEOWEEK) | +$0.25 / -$0.06 | +$0.07 / -$0.17 | +$0.14 / -$0.15 | about zero |
| Feature film box office (KXFEATURE) | -$0.42 / -$0.38 | -$0.46 / -$0.39 | -$0.35 / -$0.20 | loses |
| 2028 Dem primary (KXDPRESPRIMARY) | n/a / +$0.04 | n/a / +$0.02 | n/a / +$0.04 | almost no fills, almost no reward |
| **All 8 pooled** | **+$0.33 / -$0.22** | +$0.04 / -$0.37 | **+$0.58 / +$0.13** | **not positive in both halves** |

In dollars on the ~$1,700 the paper test parks: base about +$5.60 a day in the older half and **-$3.70 a day** in the newer half;
with the 5c pause about +$9.90 / +$2.20 a day. The forward paper test measured $1.04 a day per $100 of rewards (5.4 h, 0 fills).

**Verdict:** the rewards are real, but on most series fills eat them. Pooled, the rule is not positive in both halves. Only the two
shipping-strait weekly series are positive in both halves, and only if today's order books are a fair guide to the past (see
"Depth"). A rule that pauses both quotes for an hour after the price moves 5c or more helps in both halves pooled
and on 5 of 8 series (it was picked from 3 values on this same data, so it is a lead, not proof). Pulling quotes X hours before
the close barely matters (pooled 1 h: +$0.03 / +$0.01 better; 3 h: +$0.20 / $0.00; 24-48 h make the newer half worse). The losses come from sudden jumps
(news, a score reveal), not from the last hours. Kalshi stays paused; nothing is armed. The paper test keeps running.

## What was replayed (the same rule as tools/kalshi_rewards_paper.py)

- Window: midnight-ET days 2026-10-18 .. 2026-11-16 (30 days). Halves: the first 15 days, the last 15 days.
- Series: the paper test's three (KXRT, KXPANAMAWEEKLY, KXBABELMANDEBWEEKLY) plus five with big pools on today's active program
  list (KXART $6.5k/day, KXYTVIEWSW $3.2k, KXFEATURE $1.8k, KXEOWEEK $1.5k, KXDPRESPRIMARY $4.4k). Up to 40 markets per series,
  seeded random sample of the markets that had a liquidity program in the window (all 34 for KXEOWEEK).
- Programs: the public `/incentive_programs` history (pool, Target, discount factor, start / end; daily or weekly periods).
- Quotes: while a program runs, Q = Target/5 contracts on BOTH sides at the reward reference price, from the 1-minute candles
  (YES at the yes bid, NO at 1 - yes ask, minus the measured ticks from the best bid to the reference, usually 0). The book is the
  last closed minute, so there is no look-ahead. A moved reference is a new order at the back of the queue.
- Fills: the public trade tape. Taker sells at my YES price (or taker buys at my NO price) eat the queue ahead, then fill me. A trade
  through my price means nothing is left ahead of me: its size fills me. A fully filled side is refilled at the next quote.
- P&L: each fill to $1 / $0 at settlement, or today's mid if not settled. Maker fee only where the series charges one (all 8 are
  "quadratic": none); charging 0.0175 p(1-p) everywhere moves pooled to +$0.29 / -$0.27 (results_feeall.json).
- Parked $: resting bids (Q x price, both sides) + the cost of filled contracts still held. Net per $100 parked per day =
  100 x (rewards + fill P&L) / ($ parked x days).

## Depth (how my reward share and my queue place were estimated)

Kalshi publishes no order-book history. So the depth was measured from today's public books (`depth_snap.py`: up to 25 active
program markets per series, 3 snapshots 3 minutes apart, 2026-11-17 ~21:15 UTC) and applied to the past:
- per side and price bucket (under 15c, 15-85c, over 85c): the queue ahead of a new order (depth at prices >= the reference) and
  everyone's reward score, as multiples of Target; also the share of snapshots where both sides reach Target (valid).
- the replay is run with 4 representative books per bucket (12.5 / 37.5 / 62.5 / 87.5 percentiles by score, each with its own
  queue) and averaged, so a thin book's big share and short queue stay together.
- Median queue ahead, x Target (1,000 contracts): KXRT 22-97, Panama 4-128, Babel 2-20, KXART 2-8, KXYTVIEWSW 2-6,
  KXFEATURE 2-61, KXEOWEEK 1-12, KXDPRESPRIMARY 1-362. Valid: 100% on the shipping series, KXART, KXDPRESPRIMARY; 80% KXRT;
  79% YouTube; 64% KXFEATURE; 33% KXEOWEEK.

Weak spots: depth was probably lower before pools grew, which would make old rewards look too small and old fills too rare; the
paper test's own Panama markets (tail strikes with 55,000-191,000 contracts ahead) earn about $0.31 per $100 a day, far under the
replay's $1.73: rewards depend heavily on WHICH strike is quoted.

## Queue sensitivity (pooled, first / last 15 days)

| Queue ahead x | 0 (front) | 0.25 | 0.5 | 1 (measured) | 2 | 4 |
|---|---|---|---|---|---|---|
| Net per $100 a day | +$0.33 / -$0.12 | +$0.35 / -$0.25 | +$0.33 / -$0.24 | +$0.33 / -$0.22 | +$0.32 / -$0.21 | +$0.37 / -$0.20 |

The queue barely matters: the queues are thousands of contracts long, so almost every fill comes from a trade THROUGH the price
(a jump), and those fill you wherever you stand in line. That is the adverse selection, and it is why the 5c pause helps.

## Adverse selection rules tested (pooled, first / last 15 days)

| Rule | Net per $100 a day |
|---|---|
| none | +$0.33 / -$0.22 |
| pull 1 / 3 / 6 / 12 / 24 / 48 h before the close | +$0.36 / -$0.21, +$0.53 / -$0.22, +$0.54 / -$0.22, +$0.53 / -$0.24, +$0.52 / -$0.26, +$0.51 / -$0.30 |
| pause both quotes while the mid moved 3c / 5c / 10c in the last hour | +$0.67 / +$0.08, **+$0.58 / +$0.13**, +$0.50 / -$0.09 |

Per series with the 5c pause: better in both halves on KXRT, Panama, Babel, KXFEATURE (and KXART's one half); worse on YouTube
and KXEOWEEK.

## Next (paper only)

1. Keep the forward paper test running 24/7 on the PC (below) for 2+ weeks; judge it on rewards - fill $ per $100 a day.
2. If the owner wants a better forward rule: pick strikes by the live book's reward per $ (mid strikes, short queues) and add the
   5c pause. That is a rule change and should start a new ledger.
3. The program ends Jan 1, 2027; real money only by the owner, smallest size, one shipping market.

## The PC run (tools/kalshi_rewards_paper.py)

tools/pc_report.py (the 15-minute task OlympusPCReport) calls `maybe_run()`: one detached, below-normal child
(`--loop 720 --gap 60`, ~12 h, then a fresh one), ledger `data/kalshi_rewards/rewards_paper.json`, public summary
`data/kalshi_rewards/summary.json` ($ earned, fill $, net, days; no tickers, no PC name). A child whose ledger is 15 minutes old is
replaced, the old one sees the new token and stops. ON by default (read-only public data, like the nightly learning); off with
`LE_KALSHI_REWARDS=0` or a file `data/kalshi_rewards/OFF`. The summary rides the PC's public ntfy status post (`kalshi_rewards`)
and live.json; the Kalshi page shows it in the "Rewards test (paper)" card, else its dated copy `kalshi/rewards.json`.

## Files and reruns (`research/kalshi_rewards_bt/`, cache gitignored)

| File | What |
|---|---|
| `harvest.py` | programs, 1-minute candles, trade tape for the sampled markets -> cache/ (~1 h) |
| `depth_snap.py` | today's books -> `depth_profiles.json` |
| `backtest.py` | the replay, queue / pull / pause grids -> `results.json`, `results_feeall.json`, `headline.json` |

```
python research/kalshi_rewards_bt/harvest.py
python research/kalshi_rewards_bt/depth_snap.py
python research/kalshi_rewards_bt/backtest.py && python research/kalshi_rewards_bt/backtest.py --fee-all
python tools/kalshi_rewards_paper.py --site-copy --out research/kalshi_edge_K5/paper/rewards_paper.json
```
Cells counted: 8 series x 2 halves x 17 variants (queue 6, pull 7, pause 4) = 272 read; only the pause rule was picked from them.
