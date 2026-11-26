---
tags:
  - zeus/strategy
  - bot/blitz
  - market/nq
  - paper
type: "strategy"
key: "blitz"
---

# BLITZ (paper)

> [!abstract] The scalper on a Builder 25K. Hidden on the site, paper only.
> **On its own 25K, BLITZ is mostly an eval experiment: its real edge per trade is small.** Nothing "like a person" (structure stops, liquidity targets, swing trails, change-of-character exits) beat today's rule in 2026 H1, H2 and 2021-25. The whole account slot (buy the eval, pass, get funded, payouts at 80% to you, a new eval after a fail) pays **+$270 a month (2026 H1), +$37 (2026 H2), -$40 (2021-25)**. In H2 random directions on the same signals make about the same ($30): outside H1 the 25K is an eval lottery ($63 tickets, about 1 in 3 pass), not BLITZ's edge. Once funded, a 25K gets stuck near its floor before it pays much (funded **$108 / $0 / $2 a month**). The best use the research found is BLITZ on LIT's funded 50K while LIT is flat (+$290-300 a month per account slot), which needs LIT's 50K funded first: not built here. Account C is built so you can **see how BLITZ performs on ...

## Rules in plain words

1. **Day filter.** Trade a day only if **yesterday's 09:30-16:00 range was at least 0.8 x the average of the last 14 such
   ranges** (yesterday's included). Known before the open. (The one filter that held in 2026 H1, H2 and 2021-25.)
2. **Noise band.** For each minute of the day: sigma = the average over the last 14 sessions of |close / 09:30 open - 1| at
   that minute (today never included). Upper band = today's 09:30 open x (1 + sigma), lower = open x (1 - sigma).
3. **Checks** only at the 1-minute closes of **11:00, 11:30, 12:00 ... 15:30** (10 checks). A close **above the upper band
   = BUY**, below the lower band = SELL. While flat, a later check can enter again.
4. **Entry:** at market at the next bar's open, right after the signal close (the bot sends it about 2 s after the close;
   a signal first seen more than 50 s late is not chased).
5. **Stop:** the signal close -/+ **1.5 x the 5-minute ATR** (14 bars, Wilder; about 60 points in 2026). It sits at
   NinjaTrader as a stop order from the entry on, with an OCO limit at 20R that is never reached in practice.
6. **Trailing:** after **+1R** the stop trails **1.5R behind the best price** (a stop change at NinjaTrader, only ever tighter).
7. **Time exit:** out at market after **30 one-minute bars**, and always **flat by 15:55** (on a CME early-close day 5 minutes
   before the halt, and no entry in the last 15 minutes before it).
8. **Limits:** one position, at most **6 trades a day**, no new trade after **-3R** on the day.
How 2026's trades ended: 73% at the 30-minute clock, 20% at the stop (first stop or trail), 7% at 15:55.
Changing the rule is a config change only (`data/account_c.json` "params", `engine/blitz.rule_params`); the default stays
this rule until a research pick passes both 2026 halves and 2021-25 and the owner adopts it.

## Performance by period

| Period | Trades | Per week | Win | PF | Net | Per month | Max DD |
|---|---|---|---|---|---|---|---|
| Jan-Jun 2026 (picked on) | 220 | 8.59 | 55.5% | 1.63 | +$5,513 | +$904 | -$1,314 |
| Jul-Oct 2026 (check) | 109 | 6.99 | 55.0% | 1.49 | +$2,143 | +$577 | -$903 |
| 2026 all | 329 | 7.99 | 55.3% | 1.58 | +$7,657 | +$781 | -$1,314 |
| 2021-25 (reference) | 1869 | 8.72 | 50.3% | 1.06 | +$4,570 | +$90 | -$4,783 |

_From research/anatomy/explain.json (costs in)._

### Trades by month

_No trades in the published trade list._

## Why it wins and loses

- Jan-Jun 2026: 98 losing trades cost -$8,815: never worked 71%, worked then turned 19%, shaken out then went our way 11%, news 0%.
- Jul-Oct 2026: 49 losing trades cost -$4,351: never worked 75%, worked then turned 17%, shaken out then went our way 4%, news 4%.
- 2021-25: 929 losing trades cost -$81,497: never worked 67%, worked then turned 16%, shaken out then went our way 16%, news 1%.
- Some stops are shake-outs (wider stops were tested before and lost: the other stop-outs get bigger): a stop 50% wider would have reached +1R first on 31.0% / 29.4% / 29.9% of stop-outs (Jan-Jun / Jul-Oct / 2021-25); the median stopped trade was only +0.19R our way at best and was out in 12 min (Jan-Jun).
- A careful-human skip list (against both trends / late / news within 30 min / prior-day level under 1R ahead) flags 64% of the losing $ but also 63% of the winning $ (Jan-Jun): skipping them = -$3,419 Jan-Jun, -$2,242 Jul-Oct, -$2,676 in 2021-25.
- Why winners win (Jan-Jun): the best 20% of winners made +$7,332 (133% of the net); the median winner went only 0.27R against us first and took 31 min; 98% of winners came on days that closed our way (losers 87%).
- Hindsight, not a rule: on days that closed our way the trades made +$6,623 / +$3,009 / +$12,398, on days that closed against us -$1,110 / -$865 / -$7,828 (Jan-Jun / Jul-Oct / 2021-25). The day's direction is only known after the close.
- Known at the entry, nothing separates losers from winners better than chance: 7 of 66 fact buckets were worse (or better) in all three periods, vs 14.2 on average with the results shuffled (p 0.97).

## Tested and rejected

> [!failure]- BLITZ v2 rebuild
> 8 structural versions (noise-area band/VWAP exit, no time exit, cost gate stop >= 0.25% of price, opening-drive checks, limit at the band, first break only, 2 combos) vs today $912 / $688 / $89 a month (H1 / Jul-Nov / 2021-25). Best = V1 noise-area exit: 2021-25 PF 1.34, $352/mo, every year +, walk-forward 14/19, but 2026 $671 / $231 and on the shared 50K with LIT + ATLAS the 2026 pass falls 95 -> 87 / 88 -> 82. BLITZ today on the shared 50K: Jul-Nov pass 88.2 -> 82.5. Correlation ~0 does not help. 25K at $400: fail 43-76%; Rapid pass 0-28%. Verdict: retire BLITZ as a pillar; V1 is the only base worth reviving.
> Write-ups: [[blitz-v2-2026-11-26|BLITZ v2]]

> [!failure]- Market Learn weekly trial #1
> BLITZ half size when the prior-day level sits 4R+ ahead (picked on even ISO weeks, find z -1.46): hold-out odd weeks -$633 (p 0.51), 2021-25 net -$1,112, PF 1.06 -> 1.05. Rejected; trials.json keeps it so it is never re-tried. Seed (4,184 backtest trades, 3 pillars): strong lessons LIT 0 / ATLAS 1 / BLITZ 2 vs 0.5 / 0.5 / 1.3 by chance (p 1.0 / 0.34 / 0.31) - no context bucket beats chance.

> [!failure]- BLITZ review
> 8 pre-declared EXIT ideas on today's BLITZ (account C, $150, costs in): out at minute 10 / 15 if in a loss and never +0.5R, out at minute 10 if never +0.25R (H1 pick: +$22 Jan-Jun, -$292/mo Jul-Oct, 2-week fails 21.7 -> 40.6%), out on a 1m close back inside the noise band (from entry / from minute 10), breakeven at +0.5R, the minute-15 cut / band exit with a 45-minute hold (+$144-162 Jul-Oct, -$240 Jan-Jun). 0 pass; every one LOWERS the win rate (35-53% vs 57%): non-starters (not +0.5R by minute 10) still end near 0R in 2026. Today's BLITZ: +$963 / +$667 / +$73 a month, own 25K slot +$286 / +$52 / -$39.
> Write-ups: [[blitz-review-2026-11-18|BLITZ review]]

> [!failure]- Rule-native layer
> 2nd target / 1R / scalp / profit lock: no sooner payout. Lead only: BLITZ max 3/day on the Rapid (chance-level by count; 2021-25 2-week eval fails 2.9% -> 6.0%). Watch on paper.
> Write-ups: [[rule-native-2026-11-17|Rule-native search]]

> [!failure]- BLITZ on its own 25K, "like a person"
> as account C (never opposite LIT / ATLAS, closed first; costs $0 in 2026, $16/mo at $150 in 2021-25): structure stops (last 1m / 5m swing, the move's low, caps; 45), liquidity targets / partials / swing trails / change-of-character exits / no clock (1,920), opening drive, London band, retest limits, 15m / 1h BOS filters (32), funded-only structure rule: none beats today's rule in H1, H2 and 2021-25. 25K size: 40% of the room, 100% from eval session 5 (decided in 2 weeks 71-74% vs 29-41%, same money: slot $270 / $37 / -$40 a month; random directions make the same H2 slot $). The post-hoc 1.0 x ATR / 45 min / no trail variant is worse on LIT's 50K too (H2).
> Write-ups: [[blitz-25k|BLITZ on its own MFFU Builder 25K]]

> [!failure]- ATLAS + BLITZ edge night
> - BLITZ trend-day SIZE (range so far, first-hour range / volume, overnight range / open's place in it, gap, VIX change, 2-sigma excursion, VWAP side / distance, held at the previous check, time; 430 tilts): 39 survivors vs 36 on shuffled facts = chance. - BLITZ + a 10:30 check: H1 25K slot $270 -> $54. - BLITZ in-day streak size (2026-10-31, `blitz-streak-size-2026-10-31.md`, `tools/bzx_streak.py`, run `bzx_streak`): eval size x m after a same-day BLITZ loss / win (7 cells, 10 shuffled controls). H1 pick x0.5 after a loss: slot $286 / $53 / -$40 a month vs today $286 / $52 / -$39; 2021-25 no better than shuffled (after-loss trades are the BETTER ones there). - BLITZ cold-streak size on its ...
> Write-ups: [[atlas-blitz-edge-2026-10-30|ATLAS + BLITZ edge night]], [[blitz-streak-size-2026-10-31|BLITZ in-day streak size]]

> [!failure]- One-account combined book
> 13 books x 4 MFFU accounts (+ today = 53) on rank.py at real fills: first-come, LIT-priority 50% day budget, ATLAS NY-only / London-only / strict windows, ATLAS x0.5 eval, LIT eval then both funded, LIT x0.75 / x0.5, + BLITZ $300, ATLAS lane x2. Pick (Jan-Jun, eval fail <= LIT + 2 pts): Rapid EOD 50K LIT + ATLAS, LIT x0.5 in the eval $4,918 / $2,204 / -$88 a month vs today's 2 accounts $981 / $857 / -$62; paired 2021-25 -$156 (SE $32), 2022 -$781, Jul-Oct without ATLAS's 5 best days +$114 (SE $136): fails the 2021-25 bar, no card. Every mixing trick makes less than plain first-come in Jul-Oct (-$60 to -$1,352/mo); the gain is the Rapid 50K account (open card plan-rapid50k-max2-rebuys). ...
> Write-ups: [[one-account-book-2026-11-22|One account, combined book]]

> [!failure]- 2026-11-24 BLITZ on the Rapid EOD 25K eval ...
> 2026-11-24 BLITZ on the Rapid EOD 25K eval (research/writeups/four-pillars-2026-11-23.md, research/pillars/DESIGN.md pre-registered, 2,000 eval paths, real fills): the BUILT $300 lane fails the eval 0.5% -> 3.1% Jan-Jun (fails the +1 point bar). REJECTED: V2 no BLITZ from a LIT entry to 30 min after its exit (3.3%; LIT is done before 11:00, removes 2 of 207 trades), V3 half size once the day is at 50% of the best-day cap (3.2%), V4 one BLITZ loser and done (1.3% but lower pass than V5). PICK (paper, owner yes/no): V5 BLITZ at $150: fail 1.2 / 2.5 / 79.8%, pass 83.0 / 91.2 / 13.0%, slot +$45 / +$91 / -$1 a month vs today; noise-sized gain.
> Write-ups: [[four-pillars-2026-11-23|The four pillars]]


## Write-ups

| Date | Write-up | Verdict |
|---|---|---|
| 2026-11-26 | [[blitz-v2-2026-11-26\|BLITZ v2]] | research |
| 2026-11-26 | [[batch5-2026-11-26\|Batch 5]] | research |
| 2026-11-23 (night, run 2026-11-24 early ET) | [[four-pillars-2026-11-23\|The four pillars]] | research |
| 2026-11-22 | [[one-account-book-2026-11-22\|One account, combined book]] | research |
| 2026-11-19 | [[one-account-combo-2026-11-19\|ONE account, several bots]] | research |
| 2026-11-18 | [[win-loss-anatomy-2026-11-18\|Why we win, why we lose]] | finding |
| 2026-11-18 | [[blitz-review-2026-11-18\|BLITZ review]] | rejected |
| 2026-11-16 | [[stack-one-account-2026-11-16\|More strategies on ONE MFFU account]] | promising |
| 2026-11-13 | [[nq-new-strategies-2026-11-13\|New NQ strategies for more eval accounts]] | adopt-candidate |
| 2026-11-04 | [[2026-11-04_second_strategies_night\|Second strategies night]] | research |
| 2026-11-04 | [[2026-11-04_atlas_round3\|ATLAS round 3]] | research |
| 2026-11-03 | [[2026-11-03-slippage\|How much slippage each bot survives]] | info |
| 2026-11-03 | [[2026-11-03-night-rnd\|Night R&D 2026-11-03]] | adopt-candidate |
| 2026-11-03 | [[2026-11-03-money-plan\|The money plan on today's settings]] | adopt-candidate |
| 2026-10-31 | [[blitz-streak-size-2026-10-31\|BLITZ in-day streak size]] | rejected |
| 2026-10-30 | [[discretion-score-2026-10-30\|Discretion score for ATLAS and BLITZ]] | rejected |
| 2026-10-30 | [[blitz-edge-2026-10-30b\|BLITZ edge, rounds 2-4]] | rejected |
| 2026-10-30 | [[blitz-2026-backtest\|BLITZ]] | info |
| 2026-10-30 | [[atlas-blitz-edge-2026-10-30\|ATLAS + BLITZ edge night]] | adopt-candidate |
| 2026-10-29 | [[mind\|Mind]] | finding |
| 2026-10-29 | [[blitz-25k\|BLITZ on its own MFFU Builder 25K]] | adopt-candidate |
| 2026-10-28 | [[scalp-na-mffu\|BLITZ]] | promising |
| 2026-10-28 | [[scalp-momentum\|Momentum scalps for a third account]] | promising |
| 2026-10-28 | [[scalp-mean-reversion\|Mean-reversion scalps for a third account]] | rejected |

## Links

- [[ZEUS Lessons]] · [[ZEUS Decisions]] · [[ZEUS Home]]
