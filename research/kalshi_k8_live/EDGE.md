---
title: K8 live re-check at $2.50 / $55 (before going live Mon 2026-11-23)
family: kalshi
date: 2026-11-21
status: edge still there in-sample at $2.50; out-of-sample is only 6 bets (3 won, +$0.53); no price creep; fills fine. Pre-registered in PREREG.md
---

# K8 at your size ($2.50 a bet, $55): the honest re-check (2026-11-21)

**In plain words.** At $2.50 a bet on the 3 live legs, the history says about **+$12 a week** (about +$48 after 4 weeks).
If the real edge is 10 points weaker (the planning case), about **+$6 a week**. The stops mean the account never fell below
$30 in any simulated run. The catch: everything up to Nov 18 is the friend's own months (in-sample). Only 6 bets since then
(Nov 19-20). They won 3 of 6, +$0.53. That is far too few to tell anything. The newest week, Nov 16-20, was the worst of all 16
weeks: 6 of 15 won, -$6.54.

## What it makes (3 live legs, $2.50, exact fees, price = a $2.50 order filled from +20 s)

| Window | Bets | Won | Avg price | $ per bet | $ a week (95% range) |
|---|---|---|---|---|---|
| Full history Aug 3-Nov 20 (in-sample) | 236 | 72.9% | 51.5c | +$0.89 | **+$12.23** (+$8.15 to +$16.29) |
| Last 4 weeks Oct 26-Nov 20 (in-sample to Nov 18) | 60 | 73.3% | 52.0c | +$0.89 | +$12.32 (+$3.48 to +$20.76) |
| Out-of-sample Nov 19-20 (6 bets, tells nothing yet) | 6 | 50% | 50.2c | +$0.09 | +$1.23 (-$9.51 to +$11.97) |
| Planning case: 10 points fewer wins | | 62.9% | 51.5c | +$0.45 | **+$6.17** |

About 13.9 bets a week from Nov 23 (Thanksgiving Thu-Fri: the evening legs are skipped). Fees $18.63 over 236 bets (about 8c a bet).

## The three settings (20,000 runs each, $55 start, every stop applied, the real calendar from Nov 23)

| Setting | $ a week (history / planning) | After 4 weeks: average, bad 1-in-20 | Week stop hit, 4 wk / 12 wk | Bot OFF (drawdown stop), 4 wk / 12 wk | Below $30 | Down after 4 wk (planning) |
|---|---|---|---|---|---|---|
| **$2.50, 3 legs (current)** | +$12.23 / +$6.17 | $103 ($70); planning $78 ($42) | 8% / 22% (planning 20% / 35%) | 4% / 14% (planning 17% / 41%) | 0% | 2% (15%) |
| $2.50, gold only (2 legs) | +$8.02 / +$3.97 | $88 ($67); planning $71 ($46) | 1% / 4% (planning 6% / 11%) | 1% / 3% (planning 7% / 20%) | 0% | 1% (13%) |
| $1.00, 3 legs | +$4.03 / +$2.05 | $71 ($61); planning $63 ($53) | 0% / 0% | 0% / 0% | 0% | 1% (9%) |

- "Bot OFF" means the bot is $19.25 below its best point and can't place another bet. It stays off until you and Claude look.
  The bets don't grow as the account grows, so the same $19.25 dip can also come after a big win streak. That is why OFF climbs
  to 14% over 12 weeks even when the edge is fully there.
- The win-rate kill (under 58% won after 60 bets) fires in 21% of 12-week planning runs at $2.50. That is its job: if the edge
  is weaker, it turns the bot off.
- The price kill (over 58c on the last 30 bets) almost never fires: at most 0.1% of runs in any setting.

## Checks

- **Fills at +20 s ($2.50 = 4-5 contracts):** other traders bought at least that much of our side between 20 and 30 s on
  91% of days for gold 05:15, 100% for gold 16:45 and 94% for silver 16:45. By 45 s it is 99-100%. Median volume on our side in
  20-30 s: 263 / 1,330 / 168 contracts. $2.50 fills easily.
- **Price creep: no.** Average price paid by week: 50-51c in August, 50-54c in September and October, then 55c, 49c, 55c and
  49c over the last 4 weeks. No steady rise. The "50c to 54c" warning from Nov 19 did not continue.
- **Per leg (full history):** gold 05:15 DOWN 75% won, +$0.97 a bet. Gold 16:45 UP 70%, +$0.80. Silver 16:45 UP 74%, +$0.92.
  All three are well above zero. Silver isn't the weak leg.

## Verdict

- **The edge still looks real at $2.50, but only in-sample.** The pre-registered test passes: the full history and the last
  4 weeks are both profitable, and the last 4 weeks' range stays above $0. The 2 new days are a coin flip and can't confirm it.
- **The current setting ($2.50, 3 legs) is acceptable.** It has the most expected $ (+$12 a week, +$6 in the planning case).
  No run fell below $30. The real risk is the bot switching itself OFF: about 1 in 25 in 4 weeks, 1 in 6 if the edge is weaker.
- **Gold-only is the safer choice.** Under the pre-registered rule it counts as "better": OFF odds drop from 4% to 1% in
  4 weeks (14% to 3% over 12 weeks), and it keeps about two thirds of the $ (+$8 a week). That is a yes/no for the owner,
  because silver itself made money.
- **$1 bets** almost never trip a stop, but they make only about +$4 a week. That is less than half, so by the rule they are not better.
- The newest week was the worst again (-$6.54). Watch the first 2 live weeks. If they lose at this rate, the win-rate kill
  and the drawdown stop will turn the bot off.

Files: `PREREG.md` (written first), `fetch.py` (public GET, added Nov 20's 3 missing markets), `edge.py`, `edge.json`,
`data/tape.jsonl` (400 markets, Aug 3-Nov 20).
