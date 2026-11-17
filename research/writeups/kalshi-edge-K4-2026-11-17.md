---
title: Kalshi edge, team K4 (cross-venue Polymarket, sports, 15-min crypto slices): NO EDGE FOUND
family: kalshi
date: 2026-11-17
status: rejected - no edge found (cross-venue, sports favourite-longshot, crypto coin x hour slices)
---

# Kalshi edge, team K4 (2026-11-17): NO EDGE FOUND. Keep Kalshi paused

## Owner summary

| Idea | Test result (newest 3 weeks, fees in) | $/month at $10 a bet | Verdict |
|---|---|---|---|
| 15-min crypto: copy Polymarket's price | -9% per $1 (range -14% to -4%) | about -$10,000 (it trades a lot) | Loses |
| 15-min crypto: copy Polymarket's last-minute move | -7% per $1 (-11% to -4%) | about -$8,000 | Loses |
| Sports: copy Polymarket's price (NBA/NFL/NHL/MLB) | the two venues almost never disagree (8 bets in 3 weeks) | about $0 | Nothing to trade |
| Sports: buy favourites 75-90c before the game | +1.8% (-1.7% to +5.2%), was -2.5% before | +$507, not proven | No edge |
| Sports: buy longshots under 25c | -43% (-56% to -27%) | -$15,900 | Loses badly |
| 15-min crypto: coin x hour x minutes x side (854 slices) | 4 slices passed the strict bar, all 4 failed the test | $0 | Luck |
| "Free money" between Kalshi and Polymarket | not real (different settle prices, stale prints, Polymarket is closed to US users) | $0 | No |

**Verdict: nothing to switch on.** No paper rule file was written (`research/lab/kalshi_live_candidate.json` does not exist
on purpose). One result looked like +18% to +32% per $1. A live check showed it was a timing mistake: it used a Polymarket
price that is only published about a minute later. Done honestly, the same trade loses 9%.

## Rules used everywhere
- Kalshi's PUBLIC market data and Polymarket's public gamma / CLOB endpoints. GET only: no key, no account, no order. Nothing armed.
- Taker buys at the ask (NO side = 1 - yes bid). Kalshi fee 0.07 x C x p x (1-p), rounded up to the cent on a $10 order
  (`lib.fee_per_contract`). Edge = profit per $1 of cost. A spread over 4c (crypto) or 6c (sports) is skipped.
- Time split, test read once: crypto train 2026-09-18 to 10-28 (41 days), test 10-29 to 11-16 (19 days); sports train
  2026-06-01 to 10-25 (148 days), test 10-26 to 11-16 (23 days). 95% ranges are cluster bootstraps (crypto: one settle
  time; sports: one game). Searches use a one-sided Bonferroni bar over every eligible cell.
- $/month = test edge x bet x trades a month at full coverage (what you would take, not what the book can absorb).

## 1. Cross-venue: Kalshi vs Polymarket

**Data.** 22,788 Kalshi 15-minute up/down markets (BTC, ETH, SOL, XRP, 5,697 each) with 1-minute yes bid/ask, matched to
the same 15-minute window on Polymarket (`<coin>-updown-15m-<start>`), with Polymarket's price history (about 1 print a
minute). 798 NBA / NFL / NHL / MLB games matched to Polymarket moneylines (`<league>-<away>-<home>-<date>`; 798 of 800
settled the same way).

**The two crypto products are not the same bet.** Kalshi settles on the CF Benchmarks index against its own start
price; Polymarket on Chainlink's BTC/USD stream against its start price. They settled differently in 294 of 22,750
windows (1.3%), and their prices differ in level all the time (for example Kalshi 35c vs Polymarket 28.5c on the same
window). So no cross-venue "arbitrage" is locked in: the 70,000+ apparent arbitrage minutes are a level gap plus a
1.3% chance that both legs lose. Polymarket is also closed to US users, so the only capturable part is a Kalshi-only signal.

**Results (crypto, follow Polymarket, threshold 5c, all coins; test):**

| Rule | n train / test | Edge train (95%) | Edge test (95%) | Trades/month | $/month $3 / $10 | Max losing streak (test) |
|---|---|---|---|---|---|---|
| Copy the price, 1-3 min left | 7,766 / 3,527 | -3.4% (-11.2 to +4.9) | -9.9% (-19.4 to -0.4) | 5,600 | -$1,680 / -$5,600 | 25 |
| Copy the price, 4-7 min left | 12,324 / 5,613 | -11.0% (-15.3 to -6.5) | -6.3% (-13.3 to +0.8) | 9,000 | -$1,690 / -$5,640 | 30 |
| Copy the price, 8-13 min left | 15,179 / 7,014 | -7.7% (-10.8 to -4.5) | -9.3% (-13.8 to -4.5) | 11,200 | -$3,140 / -$10,460 | 29 |
| Same, Kalshi quote one minute later | 15,437 / 7,125 | -9.2% (-13.0 to -5.6) | -9.1% (-14.2 to -4.0) | 11,400 | -$3,120 / -$10,410 | 31 |
| Copy the last-minute move (`crypto_move.py`, 5c) | 15,469 / 7,129 | -6.4% (-8.8 to -4.1) | -7.4% (-11.2 to -3.6) | 11,300 | -$2,500 / -$8,400 | n/a |
| 192-cell search (coin x minutes x threshold x copy/average x timing) | best train t +0.67, bar 3.47 | | 0 carried | | | |

**The +18% to +32% that was not real.** Polymarket's print stamped t matches the Kalshi quote of t - 60 s much better
(2.6c gap) than the quote at t (7.5c), so I re-ran with the print treated as known a minute earlier (`--align`). That
version "won" +14% to +33% per $1 in train AND test, 65 of 180 cells past the bar. Too good to be true, so I checked it
live (`live_recorder.py`, 32 minutes, our own clock, 603 snapshots a coin): a Polymarket history print stamped t shows the
price we saw about **10 seconds before** t (gap 1.1c at -10 s, 4.1c at 0 s, 10c at +60 s). So the stamps are not late:
Polymarket simply reacts later than Kalshi, and `--align` was trading Kalshi's old quote on news from a minute later.
Lookahead, rejected. The live check did find that Polymarket's 30-second moves line up with Kalshi's next 30 seconds
(BTC correlation 0.29, ETH 0.09), but on minute data that move signal loses 7% after the spread and fee (table above).
Catching a sub-minute lead needs a second-by-second bot and a Polymarket feed; with this sample (two windows per coin)
it is a lead for later, not a rule.

**Sports cross-venue (`sports_xvenue.py`).** Kalshi's and Polymarket's moneylines differ by more than 2c beyond Kalshi's
ask in only 20 train / 6 test games an hour before the start; following Polymarket lost -47% in train (n 20) and is too
thin to read in test (n 6). 26 "arbitrage" hours in 23 of 798 games (4.6c) used Polymarket's hourly last print, not a
quote you could hit, and need a Polymarket account a US resident cannot have.

**Fed / CPI / politics.** Not tested as a strategy: Fed decisions are 8 independent outcomes a year and CPI 12, so no
time split can pass a bootstrap. Snapshot today (Dec 2026 meeting, hike 25 bp): Kalshi 90/91c, Polymarket 91/92c. They agree.

## 2. Sports favourite-longshot (`sports_study.py`)

17 Kalshi winner series (NBA, NFL, NHL, MLB, college football and basketball, WNBA, 7 soccer leagues, UFC; tennis left
out because its start time is not in the data), 72,207 trade units, hourly quotes from 24 h before to 3 h after the
scheduled start (start = expiration_time - 48 h, MLB 72 h; checked against the volume jump at the start).

| Idea (pre-registered, all sports) | n train / test | Edge train (95%) | Edge test (95%) | Trades/month (test) | $/month $3 / $10 | Max losing streak |
|---|---|---|---|---|---|---|
| Favourite 75-90c, before the game | 3,827 / 2,139 | -2.5% (-5.3 to +0.2) | +1.8% (-1.7 to +5.2) | 2,800 | +$152 / +$507 | 11 |
| Favourite 75-90c, in the game | 2,276 / 858 | -2.4% (-4.7 to -0.1) | -0.2% (-4.0 to +3.4) | 1,100 | -$7 / -$23 | 5 |
| Heavy favourite 90-98c, before | 986 / 768 | -2.5% (-6.3 to +0.9) | +2.1% (-0.8 to +4.6) | 1,000 | +$64 / +$214 | 4 |
| Heavy favourite 90-98c, in the game | 1,391 / 624 | -1.2% (-2.9 to +0.4) | +0.3% (-2.2 to +2.5) | 830 | +$8 / +$27 | 3 |
| Longshot 2-25c, before | 4,212 / 2,817 | -9.4% (-23.4 to +4.7) | -42.6% (-56.0 to -27.2) | 3,700 | -$4,770 / -$15,900 | 196 |
| Longshot 2-25c, in the game | 3,817 / 1,539 | -16.3% (-26.7 to -4.9) | -12.0% (-36.2 to +16.0) | 2,000 | -$740 / -$2,450 | 42 |
| Coin flips 40-60c, before | 15,682 / 3,559 | -4.5% (-5.4 to -3.6) | -3.4% (-5.4 to -1.2) | 4,700 | -$470 / -$1,580 | 9 |
| Cell search sport x time x price band | 121 cells, best train t +1.52, bar 3.34 | | 0 carried | | | |

The bias is there in the usual direction (longshots are overpriced), but the favourite side only earns back about the fee:
negative in five months of train, slightly positive in three weeks of test, every range includes zero. NFL favourites
(+15% test, n 230) were -9% in train: noise. No sport, no time to the start, no price band survives.

## 3. 15-min crypto slices (`crypto_slices.py`)

Coin (4) x ET hour of the close (24) x minutes left (1-3, 4-7, 8-13) x role (favourite 80-97c / 50-80c, underdog
20-50c / 3-20c) = 1,152 cells, 854 with 40+ train trades; Bonferroni bar t 3.85.

| What | Result |
|---|---|
| Cells past the strict bar on train | 4 (SOL 1 am, XRP 3 am, ETH 11 am, BTC 5 pm, all heavy favourites, 0-1 losses in about 70 bets: the t is high only because no loss had come yet) |
| Same 4 on test | +3.9% (-7.1 to +12.1), -5.4% (-20.1 to +7.6), +1.3% (-12.0 to +10.6), +5.2% (-6.8 to +12.8): none above zero, n 20-32 each, about 45 trades a month each |
| Cells with a loose t > 1.96 | 17, against 21 expected by luck alone; on test 10 positive, pooled +0.1% (-4.0 to +4.0), n 524 |

Exactly what pure luck looks like. Dead end.

## Reproduce
`research/kalshi_edge_K4/`: `harvest_crypto.py 2026-09-18 2026-11-17`, `harvest_sports.py live`,
`harvest_sports.py live x KXMLBGAME`, `harvest_sports.py hist 2026-06-01`, then `crypto_xvenue.py` (and `--align`, the
rejected lookahead version), `crypto_move.py`, `crypto_slices.py`, `sports_study.py`, `sports_xvenue.py`, `diag_lag.py`,
`live_recorder.py 32` + `live_analyze.py data/live_<ts>.json`. Compact data in `data/` (8.6 MB); the raw download cache
(`cache/`, about 1.3 GB) is gitignored. Results: `results_*.json`.

## Process notes (honesty)
- The sports study was first run before the historical quotes parsed (the /historical candles name the field `close`,
  not `close_dollars`); after the fix only the train half grew (test unchanged), the rules were fixed in advance.
- The crypto `--align` run was a second look at the test set after the first run; it was then rejected by the live
  check, not tuned.
- Not tested: resting maker orders against Polymarket moves (needs order-book replay), sub-minute lead-lag (needs a
  streaming recorder for weeks), tennis (no start time in the data).

## Tested and rejected (add to the list)
Kalshi vs Polymarket on 15-min crypto (copy price, copy move, average; all minutes and thresholds); sports moneyline
copy; cross-venue arbitrage; sports favourite-longshot by sport x time to start x price band; 15-min crypto coin x hour x
minutes x side. Earlier teams: A, B, C, K1, K3, 2026-11-04.
