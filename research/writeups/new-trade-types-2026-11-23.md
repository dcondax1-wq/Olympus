---
title: New trade types - spread, holds, event days, LIT/ATLAS rotation - 0 of 18
family: strategy
date: 2026-11-23
status: rejected
summary: Four kinds of trade that are not intraday NQ direction (NQ/ES spread, firm-legal holds, event days, a LIT<->ATLAS rotation). After a Holm correction across 18 variants, none survives, and none makes money in all three spans. Nothing live changes.
---

# New trade types (2026-11-23): REJECTED, 0 of 18

**In one line:** I tested four new kinds of trade: the NQ-vs-ES spread, holds that fit inside the firm's day, event days, and switching between LIT and ATLAS. Every rule was written down before the first run, with costs in. **None is a real edge after the multiple-testing correction, and none makes money in all three spans.** Nothing changes in the bots. Paper and branch only, nothing armed.

Code: `research/tradetypes/trade_types.py` (about 10 s). Numbers: `research/lab/trade_types.json`.
Data: TradingView NQ1!/ES1! 5m exports in `data/` (futures only). LIT and ATLAS trades come from the same stored streams as regime-guard round 3 (`account4_sim.load`, `atlas_health.stream`). They match its baseline exactly: LIT+ATLAS $6,436 / $4,016 / $242 a month.

## What it means for your money

| Lane | Best version | Jan-Jun 2026 | Jul-Oct 2026 | 2021-25 | Allowed? (MFFU / FundedNext / Lucid) | Verdict |
|---|---|---|---|---|---|---|
| 1. NQ/ES spread | S3 1-3 day, z 1.5, legs re-opened daily | -$75/mo | **-$1,780/mo** | +$183/mo (Apr-Dec 2025 only) | yes* / unclear / **NO** | no |
| 2. Holds | H2 turn of month, long 18:00->15:55 | +$768/mo | +$418/mo | +$15/mo | yes / yes / yes | no: random days do as well (p 0.13 / 0.10 / 0.49) |
| 3. Event days | E4 CPI/NFP straddle | -$179/mo | -$148/mo | -$19/mo | yes on Builder; **no on Rapid funded** (news window) | no |
| 4. Regime switch | R3 rotate to the better of LIT/ATLAS's last 20 trades | $3,698/mo (vs $6,436 today) | $2,921 (vs $4,016) | -$155 (vs +$242) | yes / yes / yes | no: worse than today in every span |
| Today, for comparison | LIT $350 + ATLAS $250 | **$6,436/mo** | **$4,016/mo** | $242/mo | - | keep |

*MFFU bans hedging only on the same underlying (NQ + MNQ count as one), and its rule says unrelated assets are allowed, so a long NQ / short ES spread reads as allowed. Its terms also ban using accounts to "hedge ... or coordinate" trades, so ask support in writing before running one. Lucid explicitly bans hedging "across correlated assets (ES vs NQ)". FundedNext bans hedging across accounts and firms but says nothing about two legs in one account: unclear.

**Holding past the close is banned at all three firms.** MFFU and FundedNext auto-close at 16:10 ET and Lucid at 16:45 ET, with no overnight or weekend holds. The textbook "buy the close, sell the next open" and 1-3-day continuous holds therefore cannot be traded. They are shown only as BANNED reference rows (X1, X2), and neither would have paid anyway. The legal versions use the fact that the MFFU day opens at 18:00 ET: an 18:00 -> 09:30 hold sits inside one firm day.

## Rules (all fixed before the first run)
- Costs: $1.90 a micro round trip, plus 1 tick a side on market fills and stops (MNQ $0.50, MES $1.25).
- Size: $250 of risk a trade, at most 20 micros (Builder 25K), and never less than 1 micro.
  - **Money catch:** a full-session NQ hold with a one-day-range stop risks about **$990-1,070 on ONE micro in 2026** ($600 in 2021-25), and the overnight version with a 0.6x stop risks about $600-650.
  - So every hold or event trade risks 2-4x ATLAS's $250. A rule that cannot be sized down to $250 does not fit a 25K's $600 daily stop.
- Spans: Jan-Jun 2026 / Jul-Oct 2026 / 2021-10-18..2025-12-31. ES starts 2025-04-14, so every spread "2021-25" figure covers Apr-Dec 2025 only.
- Significance:
  - Calendar and event holds: a placebo, the same hold on random non-event sessions of the same span, 4,000 draws.
  - Spread and straddle: a one-sided bootstrap of mean $ > 0.
  - Rotation: random switch-offs of the same number of trades.
  - A variant's p is its **worst** span (it has to hold everywhere), then **Holm** across the 18 legal variants (BH is also reported).
  - Pass = Holm p < 0.05 **and** net > 0 in all 3 spans. Rotation must beat today's LIT+ATLAS in all 3 spans.

## Full table (trades/week, win %, PF, $/month, max DD; Holm p; daily correlation with LIT+ATLAS)

| Variant | Jan-Jun 2026 | Jul-Oct 2026 | 2021-25 | worst p / Holm | corr |
|---|---|---|---|---|---|
| **1. Spread** (2 MNQ : 3 MES a unit, short the rich side) | | | | | |
| S1 intraday z(4h) 2.0, out at z 0 / z 4 / 15:55 | 7.8/wk, 52%, PF 0.75, **-$1,856**, DD -$14,279 | 7.6, 54%, 1.03, +$156, -$7,969 | 8.2, 54%, 0.75, -$1,301, -$11,726 | 0.95 / 1.0 | 0.08 |
| S2 intraday z 2.5 | 5.4, 48%, 0.72, -$1,571, -$12,806 | 5.1, 64%, 0.92, -$346, -$6,279 | 5.7, 52%, 0.87, -$455, -$8,423 | 0.91 / 1.0 | 0.05 |
| S3 1-3 day z 1.5, daily legs 18:00->15:55 | 0.8, 40%, 0.92, -$75, -$4,440 | 0.6, 30%, 0.19, -$1,780, -$8,306 | 0.6, 55%, 1.52, +$183, -$1,089 | 0.99 / 1.0 | 0.00 |
| S4 1-3 day z 2.0 | 0.4, 36%, 0.76, -$243, -$4,956 | 0.5, 50%, 0.42, -$948, -$6,462 | 0.3, 60%, 1.55, +$68, -$581 | 0.81 / 1.0 | -0.03 |
| X2 S3 held continuously (BANNED) | 0.8, 35%, 0.62, -$643 | 0.6, 20%, 0.02, -$2,339 | 0.6, 50%, 1.64, +$263 | - | -0.02 |
| **2. Holds** | | | | | |
| H1 overnight drift, long 18:00->09:30, stop 0.6 day-range | 5.0, 55%, 1.26, +$805, -$4,196 | 5.0, 46%, 0.90, **-$399**, -$3,544 | 4.9, 52%, 0.99, -$13, -$12,012 | 0.65 / 1.0 | 0.02 |
| H2 turn of month (last 1 + first 3), long 18:00->15:55 | 0.9, 63%, 2.07, +$768, -$2,180 | 0.9, 63%, 1.43, +$418, -$1,895 | 0.9, 51%, 1.02, +$15, -$4,093 | 0.49 / 1.0 | 0.06 |
| H3 pre-holiday session long | 0.2, 60%, 13.3, +$220 (5 trades) | 0.1, 50%, 0.13, -$233 (2) | 0.2, 61%, 1.39, +$38 | 1.0 / 1.0 | -0.04 |
| H4 Thanksgiving Wed + Fri long | no 2026 sample | no 2026 sample | 10 trades, 80%, 3.17, +$17 | 0.25 (2021-25 only) / 1.0 | -0.01 |
| H5 post-FOMC 14:30->15:55 with the 14:00-14:30 move | 4 trades, +$94 | 3 trades, -$46 | 0.16/wk, 44%, 0.77, -$25 | 0.79 / 1.0 | 0.02 |
| H6 next session in the FOMC-day direction | 4, 0.46, -$172 | 3, 0%, -$617 | 0.15/wk, 63%, 1.38, +$39 | 0.99 / 1.0 | 0.04 |
| X1 buy 16:00, sell next 09:30 (BANNED) | 4.8, 50%, 1.10, +$325 | 4.9, 49%, 1.00, +$6 | 4.7, 52%, 1.08, +$144 | - | 0.01 |
| **3. Event days** | | | | | |
| E1 monthly OPEX Friday long | 4 trades, +$38 | 3, PF 0.06, -$524 | 0.14/wk, 35%, 0.61, -$48 | 0.97 / 1.0 | 0.05 |
| E2 quad witching / index rebalance Friday long | 2, -$200 | 1, +$73 | 17 trades, PF 1.00, $0 | 1.0 / 1.0 | -0.02 |
| E3 quad witching last-hour fade (15:00->15:55) | 1, -$10 | 1, -$22 | 17, 53%, 0.85, -$2 | 1.0 / 1.0 | 0.01 |
| E4 CPI/NFP straddle: break of the 08:30 bar, stop the other side, 2R or 11:00 | 0.35, 22%, 0.28, -$179, -$1,485 | 0.34, 33%, 0.15, -$148 | 0.19, 46%, 0.78, -$19 (from Oct 2023) | 0.99 / 1.0 | 0.00 |
| **4. Regime switch** (LIT $350 + ATLAS $250; today = $6,436 / $4,016 / $242, DD -$1,698 / -$1,488 / -$20,462) | | | | | |
| R1 LIT only while its last 40 trades sum > 0, ATLAS always (control) | same as today (never trips) | same as today | **+$329**, DD -$13,271 | REF 0.15 / 1.0 | - |
| R2 trade only the better of LIT/ATLAS by last 40, flat if both <= 0 | 3.4/wk, PF 2.61, $2,677 | 3.0, 3.95, $2,758, DD -$876 | 2.8, 0.88, -$178 | 0.96 / 1.0 | - |
| R3 same, last 20 | 3.5, 3.82, $3,698 | 3.0, 3.18, $2,921 | 2.7, 0.90, -$155 | 0.95 / 1.0 | - |
| R4 same, last 60 | 3.1, 2.94, $2,711 | 3.0, 2.55, $1,415 | 2.7, 1.03, +$42 | 0.85 / 1.0 | - |

**Smallest p anywhere:** H5 Jan-Jun 0.076, on 4 trades. No variant has a p under 0.05 in even one span. With Holm or BH over 18 variants, every one comes out at 1.0.

## What I learned per lane
1. **The spread is a cost machine.**
   - Before costs, intraday z 2.5 earns PF 1.12 in Jul-Oct and 1.17 in Apr-Dec 2025, but 0.88 in Jan-Jun.
   - Five micros a unit pay about $19 a round trip, which turns every span red.
   - The 1-3 day version lost $6,700 gross in Jul-Oct: NQ out-trended ES for weeks, and mean reversion of the ratio does not hold over days.
   - It is uncorrelated with LIT+ATLAS (0.00-0.08), but it is uncorrelated losses.
   - **Lucid bans it outright.** Lane closed.
2. **Holds: no calendar day beats a random day.**
   - Turn of month and overnight drift make money in 2026 because NQ went up in 2026: any long hold did.
   - The placebo (the same hold on random days) is as good: p 0.10-0.65.
   - The overnight drift has nothing left in Jul-Oct (-$399/mo) and 2021-25 (-$13/mo).
   - This matches the earlier tests (edge hunt C, public-strategies 11-17). The new legal 18:00 -> 09:30 form does not rescue it.
   - **Thanksgiving this week:** 2021-25 has 10 trades, 8 wins, +$17 a month. That is too few trades to say anything and below chance after correction. Watching it on paper only is fine.
3. **Event days:**
   - The CPI/NFP straddle loses in every span. The first 5m bar after 08:30 is usually the whole move, then it whipsaws.
   - OPEX and quad-witching days have 1-4 trades a year and no edge.
   - Index rebalance days are the same dates as quad witching (Nasdaq-100 and S&P rebalance on the March/June/September/December third Fridays), so E2 and E3 cover them.
   - The Rapid funded account bans trading 2 min either side of CPI/NFP/FOMC, so E4 cannot run there anyway.
4. **Rotation (new signal: LIT vs ATLAS's *relative* record):**
   - It is worse than running both bots in every span.
   - Switching one off throws away the other's good streaks, and the trailing 20/40/60-trade record has no timing value (random switch-offs do as well or better, p 0.16-0.96).
   - R1 is close to the drift switch already rejected on 11-17, and it behaves the same: it never trips in 2026 and helps 2021-25 a little (+$87 a month, p 0.15). It is not significant, so it is not a new finding.
   - Market-weather signals were not repeated (round 3 covers them).

## Additive to LIT+ATLAS?
Every lane's daily P&L correlation with LIT+ATLAS is between -0.04 and +0.08, so **all of them are uncorrelated**. That is only worth something if the lane makes money, and none does. None is marked additive.

## Honest takeaway
Changing the *kind* of trade did not find money that LIT and ATLAS miss. The best-looking rows are just "be long NQ in 2026." The firm rules (flat by 16:10, Lucid's correlated-hedge ban) close the two lanes that are textbook edges elsewhere: overnight and multi-day holds, and pairs. The best use of the money stays the same as rounds 1-3: pass evals fast in 2026-type markets with LIT, keep ATLAS on the 25K, take payouts early.

## For the lead to record (docs/TESTED_AND_REJECTED.md)
- **2026-11-23 New trade types** (`research/tradetypes/trade_types.py`, `new-trade-types-2026-11-23.md`, `research/lab/trade_types.json`):
  - What ran: NQ/ES z-score spread intraday + 1-3 day (daily legs), overnight 18:00->09:30, turn of month, pre-holiday, Thanksgiving, post-FOMC x2, OPEX, quad witching x2, CPI/NFP straddle, LIT<->ATLAS relative rotation x3 (+ the R1 drift-switch control).
  - Result: 0 of 18 (Holm). Best worst-span p 0.49 (turn of month). All corr with LIT+ATLAS < 0.08.
  - Spread: gross PF 0.88-1.17, killed by $19/unit costs; Lucid bans NQ vs ES.
  - Holds: beat random days nowhere.
  - Rotation: worse than both bots in all 3 spans.
  - Overnight and multi-day holds: banned (flat 16:10 / 16:45).

Nothing was armed, no live_model*.json was touched.
