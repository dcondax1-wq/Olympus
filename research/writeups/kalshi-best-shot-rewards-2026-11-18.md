---
title: Kalshi best shot - the liquidity-rewards maker, scored the way Kalshi actually pays
family: kalshi
date: 2026-11-18
status: REJECTED for real money. Best idea found ($10 bids at 1c on thin reward sides) looks good on a model but is not proven; agrees with the red team
---

# Kalshi best shot (2026-11-18): rewards maker - REJECTED for live money

## Verdict in plain words

**Do not put money in.** Kalshi really pays a daily pot to resting orders, but nothing shows a small account keeps more than
the fills take away:

- **The only real forward test lost.** The PC paper test ran 0.93 days: +$12.93 rewards, -$13.54 on 3 fills = **-$0.61**
  (-$0.03 a day per $100). Days up vs down: not enough days to count.
- **The broad rule is about a coin flip.** On 32 days of public tape (6 shipping-strait series, Kalshi's real scoring, $10 bids):
  +$5.31 / +$3.85 a day per $100 in the two halves, but those rewards assume today's order books; days up vs down 17 vs 15;
  worst day -$11.81 on about $250 parked. The red team found the same kind of rule **lost $3.06 a day per $100** on the 43 hours
  of new data after the window.
- **The best idea is too small and too unproven.** A $10 bid at 1c (1,000 contracts) on the cheap side, only where the live book
  says it earns at least $1.50 a reward period: replay +$28.65 / +$31.39 a day per $100 with 0 fills and 29 up days, 0 down. But
  only about **$14-18 was ever in play** (1-2 such bids at a time, about **$4.80 a day in total**), the rewards are built on today's
  books (no history exists), it was watched forward for only half an hour, only 3 of about 40 tested cells passed (chance can do
  that), and no real payout was ever checked.
- **Expected if the owner tried $100 anyway:** realistic -$3 to +$2 a day, centred near $0 (red team range; my broad-rule replay
  sits at the top of it only because its rewards assume today's depth). **Worst case:** a 1c bid loses its whole $10 when it fills;
  five bids = -$50. The program also **ends Jan 1, 2027**.

Plan file: `research/lab/kalshi_live_plan.json`, **status "rejected"** (paper only, reasons inside). Nothing armed; Kalshi stays paused.

## What I fixed / found

| Check | Result |
|---|---|
| Kalshi's rules (help page + KalshiEX filing, amended Oct 28 2026) vs the paper test | paper scored it wrong: Kalshi shares the YES side and the NO side **separately**, and only whole levels down to where depth reaches Target count. Both fixed in `tools/kalshi_rewards_paper.py` (old ledger set aside as `*.old_formula.json`, fresh one starts) and in `research/kalshi_best_shot/lip.py` |
| $1 minimum per market program (sub-dollar programs never add up) | added. At 10 contracts a side only 4 of 53 shipping markets pay; at 50 a side 24 of 53. A $10 bid at 1c clears it on 54 of 513 scanned markets |
| Reward per $ by price (513 live markets, $10 bid) | 1c sides: median 12.8% a day per $; 36-64c sides 1.1%; 90c+ sides 0.07%. Cheap sides are where the pot is thin per dollar |
| Sweeps / refills (red team) | modelled: a trade through my price fills the whole order; a market stops after a $10 fill. Mid-priced bids lose 3-16% a day per $100 on fills |
| 5c pause | barely matters for 1c bids (+19.05/+22.43 with, +19.05/+22.43 without on HormuzPeak); not a rescue |

## Backtest table (net $ a day per $100 parked, first 16 / last 16 days, default rule)

| Series | 1c only | 1-3c | 4-10c | 11-35c | 36-64c | all prices |
|---|---|---|---|---|---|---|
| Hormuz peak | +20.49 / +23.28 | +19.00 / +22.43 | +3.31 / +1.29 | -10.05 / +1.19 | none | +2.42 / +3.98 |
| Hormuz max | (no bids) | +37.99 / +41.89 | +59.43 / +9.20 | +0.15 / +2.84 | none | +39.49 / +14.91 |
| Hormuz weekly | none | none | -0.65 / -3.00 | +0.40 / -9.68 | +29.43 / -4.21 | +0.29 / -4.82 |
| Bab-el-Mandeb | none | none | -1.30 / +29.30 | +9.45 / +10.63 | +9.69 / +5.20 | +6.94 / +8.31 |
| Panama | none | none | none | 0 / 0 | +4.09 / +3.77 | +4.34 / +4.20 |
| Suez | none | none | -0.30 / +3.57 | +0.42 / -2.27 | +6.83 / +3.69 | +1.06 / +1.48 |

"none" = no bid would have reached $1.50 for its period (the crowd is too deep). Carried (both halves positive, and still
positive with twice today's depth and a 4x shorter queue): Hormuz peak 1c and 1-3c, Hormuz max 1-3c only. Their parked dollars
were tiny ($4-8), so the per-$100 numbers do not scale. Cells read: 516 (6 series x 32 variants x 2 halves + sensitivities).

## How it was tested (research/kalshi_best_shot/)

Public GET data only, at most 1 request a second, never an order. `harvest.py` (programs, hourly candles, full trade tape,
Oct 18 - Nov 18), `books.py` / `scan.py` / `fwd.py` (today's books, 1,389 side snapshots, 126 series), `profiles.py` (others'
score and queue per series and price), `bt.py` (back of the queue, trade-through = whole order filled, hourly book = stale
quotes, $1 rule, 33 h pull before close, stop after a fill), `lip.py` (the published scoring). Weak spots: no book history
(depth from today), hourly candles, nobody ahead of us ever cancels. Tests: `python -X utf8 -m tests.test_kalshi_best_shot`
(kalshi area). Rerun: `python research/kalshi_best_shot/harvest.py KXHORMUZPEAK,...` then
`python research/kalshi_best_shot/profiles.py && /home/user/heavy.sh python3 research/kalshi_best_shot/bt.py`.
