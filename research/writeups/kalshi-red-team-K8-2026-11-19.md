---
title: Kalshi red team on K8 (the friend's 15-minute gold / silver clock bets)
family: kalshi
date: 2026-11-19
status: the numbers are real and too strong to be luck, but everything to Nov 18 is in-sample (the windows came from the friend). Paper first; live small after 120 paper bets at >= 65% won
---

# Red team on K8 (2026-11-19): the friend's gold / silver clock bets

## In plain words

K8 buys one side of Kalshi's "will gold / silver be up in the next 15 minutes?" markets about 20 seconds after three fixed
windows open on weekdays: 05:15-05:30 ET DOWN, 16:00-16:15 ET DOWN and 16:45-17:00 ET UP, gold and silver, $15 a bet.
I tried to break it. I could not find a fake edge:

- **The price is real.** A bot really can pay the study's price at +20 s: a $15 order walking the same fills after 20.0 s pays
  within 0.2c of it on average. The cheaper price at the open is taken by faster bots within 0.01 s, and the study never used it.
- **Fees and results are exact.** Kalshi's own result matches the rule (UP if the end price is at least the start price, a
  tie counts as UP) on 14,758 markets, with 1 exception.
- **It is not luck from scanning every quarter hour.** Four of the friend's six legs are the top 4 of all 364 gold/silver
  quarter-hour bets. Picking the best 6 of 364 coin flips would average 64% wins, and 67% at the 99th percentile; his six average 70%.
- **The morning leg follows London's clock.** In the one week the UK and US clocks differed, the drop moved with the London
  10:30 gold auction.

But all of this is the friend's own history. He most likely found these windows in exactly these months. The only clean test
starts now. There are also warning signs:
- The newest week was the worst of the 16: 7 of 18 won, -$75 at $15.
- The price paid crept up from 50c (October) to 54c (the last 2 weeks).
- Silver 05:30 often cannot fill $15 at +20 s.
- At $15 a bet, a normal bad stretch (-$123) is bigger than a $100 account.

**Paper first: YES. Live small only after 120 paper bets (about 4 weeks), if they win at least 65% and the average price
paid stays at or under 56c.** If the owner goes live at $15 now anyway: keep at least $250 in the account, skip silver 05:30,
and stop at 60 bets under 58% won, at a -$75 drawdown, or if the average price paid goes over 58c.

| Claim (K8, research/writeups/kalshi-metals-2026-11-19.md) | Verdict | Key number (computed here) |
|---|---|---|
| The 6 legs win about 70% and make about +30% per $1 after fees | **holds** (in-sample) | 465 bets Aug 3-Nov 18: 70.1% won vs a 52.2% break-even, **+31.5% per $1** (95% +21% to +42%); first half +33%, second half +30% |
| The +20 s entry price was really available | **holds** | the +20 s walk price is within 0.2c of the study's on average (median 0, 90th pct +2.1c); P&L at it +33.2% |
| Fees and the outcome rule are exact | **holds** | verify.py's exact fee = K8's on every bet; Kalshi's result = the rule on 7,397 gold (0 exceptions) and 7,361 silver (1) markets |
| Not luck from mining the clock | **holds** (in-sample) | the 6 legs average 70.3% vs the 99th percentile of luck, 67.1% |
| Not decaying | **weak** | 78-day trend about 0 (95% -16% to +15% per $1 per month). But November is the weakest month (+21.5%, range includes 0), the latest week is the worst (7/18), and the price went from 50c to 54c |
| $15 fills at +20 s | **holds** for gold, **false** for silver 05:30 | gold: filled by 30 s on 90-100% of days. Silver 05:30: 36% (median 3 contracts of our side traded at 20-25 s) |
| "+$587 a month at $15" | **weak** | in-sample, in the friend's own months. At $15 the deepest dip was -$123, the worst day -$92 (Nov 17), and the worst run 8 losses |

## 1. Look-ahead and the outcome rule

- **Outcome rule.** K8 books Kalshi's own `result`. On every settled 15-minute market in the K8 cache, the result equals
  "settle >= target" (a tie = UP): 7,397 gold markets with 0 exceptions (19 ties), and 7,361 silver with 1 exception (36 ties).
  The target equals the previous window's settle on 7,336 of 7,338 gold and 7,301 of 7,303 silver markets. The rule is applied
  exactly, and the start price is known when the window opens.
- **Entry timing.** K8's entry is the average price takers paid for our side 15-30 s after the open (5-45 s if nobody traded
  then: 20 of 465 bets). A bot that fires at +20 s has only what is in the book at +20 s. So I re-priced every bet four ways from
  the raw tape:

| Entry | Gap vs K8's price (mean / median / 90th pct) | All 465 bets, per $1 | Test Oct 1-Nov 18 | Last 4 weeks |
|---|---|---|---|---|
| K8: VWAP 15-30 s | - | +31.5% | +29.5% | +26.8% |
| first trade of our side at or after 20.0 s | -0.2c / 0 / +2.2c | +32.8% | +29.4% | +26.5% |
| a $15 order walking our side's fills from 20.0 s | -0.2c / 0 / +2.1c | **+33.2%** | +30.2% | +28.0% |
| the 60-second ask (a slow bot) | +0.9c / +1.4c / +10.8c | +30.6% | +28.1% | +24.3% |
| the open sweep (0-1 s, only 127 bets have one) | +4.6c cheaper | not available to a +20 s bot | | |

  K8's average was, if anything, slightly against itself: at the +20 s price, winners cost 0.4c less and losers 0.3c more.
  The open price is NOT available: on Nov 17, for example, bots bought about 1,100 gold DOWN contracts 0.01 s after 05:15:00,
  pushing DOWN from 49c to 60c. K8 never used those prices.

## 2. Fees and fills at $10-20

- **Fees.** `verify.py` recomputes ceil_to_cent(0.07 x C x P x (1-P)) per order with C = floor($15 / price). It gives exactly
  K8's fee on every bet. The bet list's 3-decimal prices move the total by $0.92 over 465 bets; one contract more or fewer on
  15 bets explains the rows that differ by over 2c. No look-ahead row (decision at the open, order at +20 s), no double count.
- **Fills.** Kalshi publishes no order-book history, so I measured how fast OTHER takers' buying of our side after 20.0 s added
  up to our order. This is a lower bound: the book may have held more than anyone took.

| Leg | Our side traded 20-25 s (median contracts) | $10 filled by 30 s / 45 s | $15 | $20 | 90th pct extra paid at $15 |
|---|---|---|---|---|---|
| 05:30 DOWN gold | 98 | 92% / 99% | 90% / 99% | 82% / 99% | +0.8c |
| 05:30 DOWN silver | **3** | 46% / 86% | **36% / 76%** | 30% / 64% | +2.8c |
| 17:00 UP gold | 488 | 100% / 100% | 100% / 100% | 100% / 100% | +0.3c |
| 17:00 UP silver | 66 | 91% / 97% | 85% / 97% | 79% / 97% | +1.0c |
| 16:15 DOWN silver | 23 | 85% / 100% | 76% / 100% | 71% / 100% | +3.0c |
| 16:15 DOWN gold | 575 | 96% / 100% | 95% / 100% | 95% / 100% | +1.2c |

  Gold fills $15-20 easily. Silver 05:30 is thin: on most days a $15 order at +20 s would either wait or pay up. The friend's
  bot (and any copycat) buys in the same seconds, which is the reason to expect slightly worse fills than any backtest shows.
  K8's own check, every fill 2c worse, still left +25% per $1 on the test half.

## 3. Multiple testing and the friend-selection bias

- **What could have been scanned:** 182 gold and silver quarter-hour windows with at least 60 weekdays in Aug 3-Nov 18, times 2
  sides = 364 bets. On these 78 days the four best of all 364 are silver 17:00 UP (74.4%, z +4.3), silver 16:15 DOWN (74.4%,
  z -4.3), gold 05:30 DOWN (73.1%, z -4.1) and gold 17:00 UP (70.5%, z +3.6). Those are exactly four of the friend's six; his
  other two are gold 16:15 DOWN (65.4%) and silver 05:30 DOWN (64.1%).
- **Luck baseline:** I simulated 2,000 cases where every one of the 182 windows is a coin flip, picking the better side and
  keeping the best 6. Their average win rate has a median of 64.3%, a 95th percentile of 66.1% and a 99th of 67.1%. **The friend's six
  average 70.3%**, and three of them clear the two-sided Bonferroni bar for 364 tries (|z| >= 3.64). Even if every quarter hour
  was mined, luck alone does not explain the top legs. The weaker two (silver 05:30, gold 16:15) are not distinguishable from
  luck on their own.
- **But the friend chose the windows from this same history.** So there is no out-of-sample half: K8's "train Aug-Sep / test
  Oct-Nov" split is honest about K8's own choices, but the friend saw both halves. Everything up to Nov 18 counts as in-sample.
- **Correlation:** gold and silver in the same window win or lose together (rho 0.41 at 05:30, 0.59 at 17:00, 0.56 at 16:15;
  other pairs about 0). Six bets a day are worth about 6 / 1.6 = 3.7 independent bets (design effect 1.6). Every range above
  resamples whole days.

## 4. The clocks (DST / London) and holidays

- In Oct 26-30 the UK was already on GMT and the US still on EDT, so 10:30 London was 06:30 ET:
  - **gold**: the 05:15-05:30 ET window fell on 2 of 5 days and the 06:15-06:30 ET window on 5 of 5. On the other 73 weekdays
    they fell 55/73 (75%) and 32/73 (44%). The gold leg follows London's 10:30 auction.
  - **silver**: 3/5 and 3/5 that week (other days 47/73 and 35/73). That does not decide it either way.
- **Now:** both countries are on standard time, so 10:30 London = 05:30 ET on every weekday until Mar 12, 2027. The windows
  used now are right for the coming weeks. **Mar 15-26, 2027 (10 weekdays):** the morning legs must use 06:15-06:30 ET (US on
  EDT from Mar 14, UK on BST from Mar 28).
- **Skip days.** The 05:30 legs should skip UK bank holidays, when there is no LBMA auction: Dec 25, Dec 28 (Boxing Day moved),
  Jan 1. The 17:00 / 16:15 legs should skip US holidays and CME early closes (Thanksgiving Nov 26 and the half day Nov 27, Dec
  24-25, Jan 1): the "CME close" they lean on is not at 17:00 on those days. These days were not in the test.

## 5. Is it decaying?

| Month | Bets | Won | Paid | Per $1 (95%) |
|---|---|---|---|---|
| Aug | 123 | 67.5% | 52.3c | +26.0% (+5% to +48%) |
| Sep | 132 | 75.8% | 52.3c | +39.9% (+23% to +58%) |
| Oct | 132 | 68.9% | 50.3c | +34.2% (+14% to +53%) |
| Nov 1-18 | 78 | 66.7% | 53.1c | +21.5% (-8% to +48%) |
| **Last 4 weeks (Oct 22-Nov 18)** | 120 | 67.5% | 52.8c | **+26.8% (+4% to +49%)**: +$490, about +$123 a week at $15 |
| Last 2 weeks (Nov 5-18) | 60 | 70.0% | 54.1c | +23.8% (-13% to +56%) |

- The 78-day trend of the daily result is flat: -0.05% per $1 per month (95% -16% to +15%).
- The week of Nov 16 (Mon-Wed, 18 bets) is the worst of all 16 weeks: 39% won, -$74.94 at $15. Nov 17 lost all 6. Resampling
  whole days from Aug 3-Nov 13, a 3-day stretch that bad (7 or fewer wins of 18) comes up 1.2% of the time (1 in 82). It is a
  real warning, not proof: over 78 days, one such stretch somewhere is not rare, but this one is the newest.
- Last 4 weeks per leg (20 bets each): gold 05:30 +33%, silver 05:30 +11%, gold 17:00 +52%, silver 17:00 +24%, silver 16:15
  +28%, gold 16:15 +12%. All are positive, but only gold 17:00's range clears zero on 20 bets.

## 6. The money at $15 (the owner's size)

On the 78 days (in-sample), the 6 legs at $15 made +$2,233 (about +$143 a week; the last 2 weeks +$108 a week). The worst day was Nov 17 (-$92.16), the deepest dip -$122.70, the
worst run 8 losses, and 24 of 78 days lost. The deepest dip at other stakes: $10 -$81, $8 -$65, $5 -$40. Two bets are open at
once ($30 at $15). **A $100 account at $15 a bet can be wiped out by a normal bad stretch.** At $15, keep at least $250
(twice the deepest dip); with $100, bet $5-8.

## 7. What forward evidence would convince me

The break-even win rate at 54c plus the fee is 55.75%. A pass mark below has only a 5% chance of being reached if the edge is
gone, using the 1.6 design effect:

| Paper bets (6 a weekday) | Weeks | Pass if won at least | Chance to pass if it keeps its Aug-Nov form (normal / resampled days) |
|---|---|---|---|
| 60 | 2 | 69.1% | 44% / 55% |
| 90 | 3 | 66.6% | 59% / 75% |
| **120** | **4** | **65.2%** | **70% / 83%** |
| 150 | 5 | 64.2% | 79% / 89% |
| 180 | 6 | 63.4% | 85% / 93% |

What else must hold:
- The average price paid stays at or under 56c. Above that, the crowd is pricing the clock.
- Fills are logged at the real +20 s ask, not at the 15-30 s average.
- The legs keep their sign separately. Drop a leg that wins under 55% over its first 40 bets.

**Verdict: paper first: YES. Live small after 120 paper bets if win rate >= 65%** (and the average price paid <= 56c),
starting at $5-8 a bet with $100, or $15 only with at least $250 in the account. Kill rule, paper or live: stop at 60 bets
under 58% won, at a -$75 drawdown at $15 (-$40 at $8), or at an average price over 58c.

## Files and reruns (`research/kalshi_red_team/`, offline on the K8 cache /home/user/kalshi_cache/kmetal, read only)

| File | What |
|---|---|
| `k8_check.py` | outcome rule, the four entry prices, fees through `verify.py`, months / weeks / last 4 weeks, the London week, the luck baseline -> `results_k8.json` |
| `k8_more.py` | fills for $10 / $15 / $20 after 20 s, gold-silver correlation, the forward pass marks, the 78-day trend -> `results_k8.json` |

```
python research/kalshi_red_team/k8_check.py && python research/kalshi_red_team/k8_more.py
```
No network, no key, no order: both scripts only read the K8 cache and `research/kalshi_edge_K8/data/legs_bets.csv`.
