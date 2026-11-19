---
title: Kalshi red team, the liquidity-rewards lead checked from raw data (paper test, tape backtest, Kalshi's filed rules)
family: kalshi
date: 2026-11-18
status: NOT safe to go live. The rewards are real, but no net edge is shown for a small maker; the 2 best-looking series lost in the first 43 h of new data. Verifier built (research/kalshi_red_team/verify.py)
---

# Kalshi red team (2026-11-18): is the rewards lead a real edge?

## In plain words

Kalshi really does pay people who leave orders waiting in the book ("liquidity rewards"). The Nov 17 programs the paper test
watched have been paid out. The catch is the other half: a waiting order mostly gets filled when someone sweeps the book just
before the price moves, and one such fill can wipe out a week of rewards. Nobody has shown that a small trader comes out ahead
after those fills:

- The paper test ran for only 7.8 hours (Nov 17) and got ONE fill. It is not running anywhere now: its last write was Nov 17 23:03 UTC.
- The 30-day replay can be rebuilt exactly from the public tape. With Kalshi's real formula, the two shipping series even look
  better on those 30 days (+$1.2 to +$1.9 a day per $100). But they were kept BECAUSE they looked good: 2 of 8 series, and luck
  alone gives at least 2 of 8 positive halves 63% of the time. In the first 43 hours of NEW data after the replay window, the same
  rule on the same two series LOST $3.06 a day per $100 at the owner's size, because fills ate the rewards twice over.
- At $50-100, Kalshi's $1.00 minimum per market per day pays $0 on 33 of 42 live markets at 50 contracts a side. The thin
  markets that do pay are the ones that get swept. The best live market today lost $67.84 on fills last week against $20.16 of
  rewards (50 a side). In the replay, one market lost $159 in one day at 50 a side because the order kept refilling as the price fell.
- The program ends Jan 1, 2027 (six weeks), and Kalshi can change or end it any day.

| Claim | Verdict | Key number (computed here) |
|---|---|---|
| Kalshi pays real rewards and the paper test credits them about right | **holds** | all 9 of the paper's Nov 17 programs are paid out; Kalshi's formula pays 1.31x the paper's (median of 42 live books), before the $1 minimum |
| Paper test: +$4.32 net in 7.8 h (+$0.75 a day per $100) | **weak** | 1 fill in 7.8 h; its fill model under-fills sweeps; stopped Nov 17 23:03 UTC; its 2 best markets (77% of the reward) were swept through its quotes within 24 h |
| Replay: 8 series pooled are not positive in both halves (+$0.33 / -$0.22) | **holds** | code and numbers reproduced exactly on my re-harvest (Panama +$1.13 / +$1.38, Bab-el-Mandeb +$1.89 / +$0.76; published +$1.13 / +$1.40, +$1.89 / +$0.75) |
| Panama + Bab-el-Mandeb positive in both halves = a real edge | **weak** (luck + selection) | in-sample with Kalshi's formula: pooled +$1.91 / +$1.22. But 2 of 8 is what luck gives (63%), the series were picked on the same days, and the 43 h of new data: **-$3.33 a day per $100** (rewards +$2.20, fills -$5.53, both series negative) |
| The 5c pause helps | **weak** | best of 3 thresholds on the same 30 days (+$2.43 / +$1.77); new data -$2.22 |
| K5 estimate "+$150-470 a month on 3 markets" | **false** (as a forecast) | it assumed fills at the reward share; the best live market's fills lost 3.4x its rewards last week; the pace on new data is negative |
| A $50-100 account earns as much per $ as $1,700 | **false** | the $1 daily minimum: spread over all live markets, $0.83 (50 a side) and $0.53 (25 a side) a day per $100, vs $1.16 at 200 a side |

**Safe to go live with $50-100: NO.** Nobody has shown a net profit after fills for a small order at the back of the queue. The
two best-looking series lost about $3 a day per $100 in the first two days of new data. The paper test saw one fill. Kalshi's $1
minimum zeroes most small rewards. One bad market-day in the replay lost more than $100 at 50 contracts a side. And the program
ends in six weeks. A realistic range is about -$3 to +$2 a day per $100 (-$90 to +$60 a month), centred near $0, with a bad week
around -$20 per $100.

## 1. Kalshi's rules as filed (what any model must match)

Sources: KalshiEX self-certification to the CFTC "Amendment to August 2025 Liquidity Incentive Program" (Oct 14, 2026, effective
Oct 28, 2026, Appendix B terms) and help.kalshi.com article 13823851 (read 2026-11-19).

- The book is snapshotted once a second, at a random moment within the second.
- Per side (YES bids; a YES ask counts as a NO bid): Kalshi walks down WHOLE price levels from the best bid, adding them until the
  size reaches the Target (1,000 contracts here). The reference price is the level where the size first reaches Target / 5.
  Only the levels walked qualify; nothing below the level that completes the Target counts. Time priority inside a level does
  not matter.
- Score = size x 0.5 ^ (ticks below the reference); an order at or above the reference scores its full size. Scores are
  normalised PER SIDE: a user's snapshot score is his share of the YES side plus his share of the NO side (2.0 per snapshot in all).
- A snapshot is excluded if the market is closed or either side is under Target. It pays nobody, and the pool shrinks by that share.
- Payout per market per Time Period: share x pool x the valid share, paid only if it is at least $1.00, rounded down to the
  cent, within a day (the help page says a daily run from about 6 am ET). Time Periods are 1-7 days under the amendment (the
  help page still says up to 31). The three series here run DAILY periods, 05:00-05:00 UTC, $100 each.
- Who: most US members. Excluded: Kalshi affiliates, IB / FCM customers, and market makers with an agreement in that market.
  Orders under inquiry for spoofing, layering or wash trading earn nothing. The program ends no later than Jan 1, 2027, and
  Kalshi can end or change it at any time (press reports say its separate volume-rewards program is being wound down early).

## 2. The paper test, rebuilt from raw data

The ledger (`research/kalshi_edge_K5/paper/rewards_paper_snapshot.json`) covers 2026-11-17 15:13-23:03 UTC (7.83 h). It watched
9 markets (3 Rotten Tomatoes, 3 Panama weekly, 3 Bab-el-Mandeb weekly) with 200 contracts a side at the reference price, about
$1,763 parked. Reward $6.00, fills -$1.68, net **+$4.32** (= +$0.75 per $100 parked per day). Rebuilt with `paper_fetch.py` +
`audit_paper.py` (public tape, 1-minute candles, program list, 2 rounds of 50 live books; 145 GET requests):

| Check | Result |
|---|---|
| Programs | all 9 markets had a $100 / day DAILY program on Nov 17 (Target 1,000, discount 0.5); Kalshi marks them paid out |
| Reward per market-day | $18.63 a day over the 9 markets. **77% came from 2 markets** (RT Dune >= 87: $10.14; Bab-el-Mandeb >= 170: $4.25). The other 7 earned $0.18-1.09 a day |
| $1 minimum | 6 of the 9 markets earn under $1 a day and would be paid **$0**. Paid total: $15.47 a day (-17%) |
| The formula | The paper pools both sides. Kalshi normalises per side and drops levels past the Target. On 42 live books (Nov 19, 200 a side), Kalshi's formula pays a median **1.31x** the paper's, and 1.41x on the total ($103.66 vs $73.29 a day). On this point the paper's reward is conservative |
| The one fill | Panama >= 205 NO, 28 @ 91c. On the tape, a 579-contract sweep at 22:29:18 UTC bought YES at 9c. An hour later the mid was 17c (this fill -$2.24); now it is 9.5c (-$0.14). The fill is real and consistent with the paper's queue model |
| Fill model bug | A trade THROUGH the paper's price is first charged to the stale queue ahead, so sweeps under-fill the paper order. The paper therefore under-counts exactly the bad fills. The backtest fixed this; the paper test did not |
| After it stopped | Nov 18 21:05 UTC: a ~20,000-contract wave bought YES through the paper's Dune >= 87 NO bid at 44c. A 200-lot ($88) would have filled; the mid went 55c -> 60.5c (-$9 now, -$88 if the score ends >= 87). Nov 18 00:20 UTC: a 214-contract sweep went through the Bab-el-Mandeb >= 170 NO bid at 9c (about flat now). Both of the paper's best markets were swept through its quotes within 24 h |
| Shares move | Dune >= 87 paid $10.14 a day at 200 a side in the paper window and **$1.89** on the Nov 19 book (depth ahead on the YES side went 488 -> 7,227) |

Verdict on the paper claim: the reward credits HOLD (they are real and, before the $1 minimum, conservative). The net profit is
WEAK evidence. Fill losses are the whole question, 7.8 hours with one fill cannot measure them, and the test has stopped.

## 3. What the paper test cannot see (and what it costs)

| Blind spot | Measured here |
|---|---|
| Adverse selection | Makers as a group on the public tape (K5's per-market data, closes after Oct 15), before rewards: fills lose 2.7% (RT), 5.1% (Panama), 6.1% (Bab-el-Mandeb), 10.1% (Hormuz), 25.9% (YouTube) per $1 filled. New data (Nov 17-19), the 2 shipping series: fills **-$5.53** a day per $100 against +$2.20 of rewards. Best live market today (RT "FUR" >= 80, 50 a side, last 7 days): **71 fills, -$67.84** against $20.16 of rewards |
| Which strikes | Replay, by the price of the side quoted: bids under 15c lose 90-100% of every $1 filled (they fill as the price collapses to 0): -$10 to -$22 a day per $100 resting on Panama. Mid strikes paid +$1 to +$6 |
| Queue position | Joining the back of the queue protects you from the small, harmless fills but not from sweeps, which fill every order at the level. The fills you DO get are the bad ones. The backtest's own queue table: queue length barely changes the result |
| Partial fills / refills | In a trending market the refilled side keeps buying the losing side. RT "FUR" >= 80 filled $723 on a 50-lot quote in one week. In the replay, Bab-el-Mandeb >= 185 lost **$159 in one day (Oct 20) at 50 a side** |
| Cancels | The paper re-quotes every 60 s at no cost. Real money needs an API key and a bot that never sleeps. A quote left resting through news is the worst case, and the PC has not reported since Nov 7 |
| Pool shared with others | Shares jump from day to day (Dune >= 87: $10.14 -> $1.89 a day). K5's pool per $1 of fills halved between closes before and after Oct 15 (Panama 23% -> 12%, Bab-el-Mandeb 23% -> 12%) |
| $1 minimum per market-day | Live books, Nov 19: 19 of 42 markets pay $0 at 200 a side, 33 of 42 at 50 a side, 38 of 42 at 25 a side. Paid reward per $100 parked per day, spread over all of them: $1.16 / $0.83 / $0.53 |
| Fees on fills | The three series have fee type "quadratic": no maker fee (the verifier confirms $0 on all 662 replayed fills). Selling early costs the taker fee, 0.07 x C x P x (1-P) rounded up |
| Capital lock | A filled contract is stuck until settlement; RT markets settle when the score is final, weeks later |

### Realistic net per $100 a day at the owner's size

| Scenario (50 contracts a side unless noted) | Rewards | Fills | Net per $100 a day | Note |
|---|---|---|---|---|
| Replay, Panama + Bab-el-Mandeb, Kalshi's formula + $1 minimum, first / last 15 days | +$2.03 / +$1.50 | -$0.08 / -$0.28 | **+$1.95 / +$1.21** (95% +0.15 to +3.39 / +0.12 to +2.45) | in-sample, series picked on these days |
| same, 25 a side | +$1.71 / +$1.25 | +$0.07 / -$0.33 | +$1.78 / +$0.92 (ranges include 0) | the $1 minimum bites harder |
| New data, Nov 17 05:00 - Nov 19 00:00 UTC (43 h, 40 markets, 110 fills) | +$2.31 | -$5.38 | **-$3.06** (95% -8.99 to +0.61) | out of sample, same rule |
| Today's 5 best live markets, last 7 days | +$1.97 | -$1.61 | +$0.36 | rewards at today's share all week = optimistic |
| Bad week | | | about **-$21 per $100** | the new-data pace x 7; the in-sample worst week at 25 a side was -$2.07 per $100 |
| Bad day | | | **-$159** in one market | Bab-el-Mandeb >= 185 on Oct 20, refills into a falling price |

In dollars on $100: realistically about -$3 to +$2 a day (-$90 to +$60 a month), centred near $0, before the time a bot needs and
the risk that it stops with quotes resting.

## 4. The tape backtest, re-checked

Re-harvested with `harvest_bt.py`: the same seeded 40-market samples for Panama and Bab-el-Mandeb (372 / 468 programs, 55 / 67
markets, as published), plus the days after the window, at 1 request a second. `audit_bt.py` runs the backtest's own `sim()`
and an equivalent `sim2()` with three switches (checked identical to `sim()` when the switches are off).

**Look-ahead (code review + the verifier):**
- Quotes use the last 1-minute candle closed at or before the moment, and the 5c pause looks back one hour: both are causal. The
  verifier on the 662 replayed fills (Panama 212, Bab-el-Mandeb 450) finds **no fill whose quote used information from the fill's
  own time or later**.
- Unsettled markets' fills are marked at the harvest-day mid. That is an evaluation choice, not a decision leak.
- BUT the order-book depth (the queue ahead and everyone's reward score) comes from ONE afternoon (Nov 17, 21:15 UTC, 3
  snapshots, up to 25 markets per series) and is applied to all 30 days before it. That is information from the future, and it
  sets the whole reward line, since the measured share IS the reward. It cannot be checked: Kalshi publishes no book history.
- Capital in filled contracts is never released after the fill (until the market's quoting ends). This shrinks the per-$
  numbers in both directions; minor.

**Selection and survivorship:**
- K5 chose the 3 paper series from 11 because their fills + pool looked best on markets closing after Oct 15. That window covers
  27 of the backtest's 30 days, so "positive in the backtest" partly repeats the selection.
- The other 5 series were chosen by TODAY's pool size.
- Cells read: 8 series x 17 variants x 2 halves = 272. The 5c pause was the best of 3 thresholds on the same data. Mine: 7
  variants x 2 series x 3 windows + 4 variants on the new days, all sensitivity checks; no rule was chosen from them.

**Luck:** Two of 8 series positive in both halves is what luck alone gives: 63% for at least 2 (`verify.chance_both_halves(2, 8)`).
Resampling markets, every single half's 95% range includes zero:

| Series (base rule) | First 15 days | Last 15 days | New 43 h |
|---|---|---|---|
| Panama | +$1.13 (-0.09 to +2.24) | +$1.38 (-0.81 to +4.21) | **-$1.99** (-8.22 to +1.08) |
| Bab-el-Mandeb | +$1.89 (-0.88 to +3.94) | +$0.76 (-0.09 to +1.47) | **-$4.25** (-13.81 to +0.93) |
| Both, pooled | +$1.60 (-0.13 to +2.97) | +$0.97 (-0.01 to +1.90) | **-$3.33** (-8.94 to +0.23) |
| Both, Kalshi's per-side formula | +$1.91 (+0.21 to +3.23) | +$1.22 (+0.27 to +2.17) | -$3.02 (with the $1 minimum) |
| Both, 5c pause (per-side) | +$2.43 (+0.84 to +3.69) | +$1.77 (+0.78 to +2.76) | -$2.22 (-7.94 to +1.39) |

Kalshi's real formula makes the in-sample numbers BETTER (+20% reward), and both halves then clear zero. That is still a pick
of the best 2 of 8 series on the same days, though, and the next 43 hours went the other way: rewards held (+$2.20 a day per
$100) while fills cost -$5.53 across 160 fills. Two days is short, but every in-sample week was better than that pace.

## 5. The verifier (`research/kalshi_red_team/verify.py`)

One command checks any candidate's trade list (JSON or CSV) before anyone believes its number:

```
python research/kalshi_red_team/verify.py TRADES.json --rules-tried 40 [--split 2026-11-01] [--stake 10] [--out report.json]
```

- Fees are recomputed exactly: ceil_to_cent(0.07 x C x P x (1-P)) per ORDER. Rows sharing an `order_id` are rounded once. The
  maker fee is 0 unless the series charges makers, then 0.0175; `fee_rate` overrides (e.g. 0.035 on index markets). Reported fees
  or P&L that do not match are listed.
- Timing: every row needs `info_ts` STRICTLY before `ts` (equal counts as look-ahead), and no trade at or after `settle_ts`. A
  repeated trade id is a double count.
- Split by time (median, or a date): win rate, break-even win rate, net per $1, and a seeded cluster-bootstrap 95% range for each half.
- Luck: a cluster t, its one-sided p, and the Bonferroni bar for the number of rules tried (it warns when that number is not
  stated), plus `chance_both_halves(k, n)`.
- Verdict: false (look-ahead or data problems, or not positive after exact fees), weak, or holds (all checks pass).

Tests: `python -m tests.test_kalshi_red_team` (42 checks; in `tests/run_area.py kalshi`). On the backtest's own fills
(maker, before rewards), the verifier finds no timing problem and $0 fees. Fills alone come to Panama -6.2% per $1 (95% -25.5%
to +12.4%) and Bab-el-Mandeb -0.03% (-8.7% to +6.5%): the rewards have to carry everything.

## 6. The other helpers' results (rewards go-live plan, K6, K7)

None had arrived by the time of this commit: the three helpers were still working and nothing was committed in their
worktrees. One early check on the go-live plan's DRAFT caps ($50 in all, $10 per market, $10 daily stop; still placeholders,
not its result): on the 42 live books of Nov 19, **10 contracts a side (about $9 a market) clears Kalshi's $1-a-day minimum on
0 of 42 markets** (the best pays $0.73 a day), 15 a side on 1, 20 a side on 2. At $10 a market the rewards would be $0 while
the fill risk stays. When the results arrive, each claim goes through the same gate:

```
python research/kalshi_red_team/verify.py <their trade list .json/.csv> --rules-tried <every cell they read> --split <their split date>
```

What decides it, in order:
1. Every trade's information must come strictly before the trade. The K4 +18-32% was a look-ahead of exactly this kind.
2. Fees must be exact, per order.
3. Both time halves must be positive, with the bootstrap range above zero.
4. The t must clear the multiple-testing bar for the number of rules tried.
5. The $ a month must be shown at the size the owner would really use.

For "carry" plays (K7: near-certain, high win rate), the number to beat is the break-even win rate at the price paid plus fees.
At 95c that is 95.4% (10 contracts, fee 4c), so 50 wins and 1 loss is not yet evidence. The rewards go-live plan must show
rewards minus fills at 25-50 contracts a side, using Kalshi's per-side formula, the $1 daily minimum and the through-trade fill
rule. It must also say what stops refills into a falling price, and it must be tested on days after the plan was written.

## Files and reruns (`research/kalshi_red_team/`; raw data in /home/user/kalshi_cache/kred/, not committed)

| File | What |
|---|---|
| `fetch.py` | GET-only client: at most 1 request a second across processes, gzip cache outside the repo |
| `paper_fetch.py`, `audit_paper.py` | the paper test's raw data -> `results_paper.json` (rules check, $1 minimum, fills, live-book formula check) |
| `thin_stress.py` | today's 5 best live markets at 50 a side, last 7 days of tape -> `results_thin.json` |
| `harvest_bt.py`, `audit_bt.py` | the backtest's raw tape re-harvested (same seeded sample) + the days after it -> `results_bt.json` |
| `verify.py` | the reusable verifier (section 5) |

```
python research/kalshi_red_team/paper_fetch.py && python research/kalshi_red_team/audit_paper.py
python research/kalshi_red_team/thin_stress.py --fetch
python research/kalshi_red_team/harvest_bt.py KXPANAMAWEEKLY,KXBABELMANDEBWEEKLY --window bt
python research/kalshi_red_team/harvest_bt.py KXPANAMAWEEKLY,KXBABELMANDEBWEEKLY --window oos --until 1795046400
python research/kalshi_red_team/audit_bt.py          (small: about 85 MB, 30 s)
```
About 800 GET requests in all (public market data, at most 1 a second, no key, never an order).
