---
title: ONE account, several bots - Zlarior + ATLAS (+ BLITZ) on a Builder 50K, Builder 25K or Rapid EOD 25K
family: risk
date: 2026-11-19
status: done - paper only. On the Builder 50K, Zlarior + ATLAS on the same account (each at its own size, one position at a time, first in keeps it) beats Zlarior alone in Jan-Jun, Jul-Oct AND 2021-25 (pre-registered rule) - one Decide card. Builder 25K and Rapid EOD 25K - no combo beats today's setup in every period. Nothing live changed.
summary: Owner 2026-11-19 - "one account trade a lot of times for NQ with multiple strategies ... 25K or 50K Builder ... or a 25K Rapid EOD - don't give me bullshit results". Design committed before any result (4e682267). Bots as they are today (Zlarior 120 + 511 trades, ATLAS raw members, BLITZ alone, the post-close lead as a sensitivity), one net position (first-in; same-side adds as a sensitivity), every bot sized from ONE shared room by its own live rule (and by engine/rapid's one-account lane rule), MFFU rules per plan, owner's CLUB prices, costs in (+1 tick sensitivity), whole-day bootstrap 2,000 x 126 sessions, the same paths for every row. 160 rows x 3 periods = 480 results; 54 rows judged against today's setup. Builder 50K, $ a month after fees - Zlarior alone $827 / $714 / -$7, Zlarior + ATLAS $1,888 / $1,286 / $44 (eval median 5-7 days instead of 9-10, 60-day fails 9-13% unchanged in 2026, but 2-week fails 0.1% -> 2-4%, 2021-25 0.5% -> 34%). Adding BLITZ too - $2,242 / $1,443 / $34 but eval fails double (22-25%) and one BLITZ trade can risk $2,100. Placebo - with ATLAS's edge set to zero the combo makes LESS than Zlarior alone ($388 / $529), so the gain is ATLAS's edge, not extra variance. By year - wins 2023 / 2024 / 2025, loses 2022 (-$113 a month vs Zlarior alone). Account - Builder 50K wins of the three asked (2x the room per $ of fee, 40 micros, no eval best-day rule); the Rapid EOD 25K's 30% / 4-day eval takes 25-31 days and its funded accounts get stuck often; Builder 25K pays about half of the 50K.
runs: none (research/lab/combo_account.json, research/lab/combo_account_honesty.json)
---

## For the owner (one minute)

**Yes - more bots on one account makes more money, but only the right pair, on the right account.** Put ATLAS on
Zlarior's Builder 50K (one position at a time, the first one in keeps it). Do not add BLITZ, do not do it on a 25K or a
Rapid EOD 25K.

| What ($ a month to you after the eval fees, 6 months; 10-90% of runs) | Jan-Jun 2026 | **Jul-Oct 2026** | 2021-25 |
|---|---:|---:|---:|
| **Builder 50K, Zlarior alone (today)** | $827 | **$714** | -$7 |
| **Builder 50K, Zlarior + ATLAS (the proposal)** | **$1,888** ($1,287-$2,605) | **$1,286** ($751-$1,836) | $44 (-$153 to $457) |
| ... the gain over today (same runs) | +$1,060 ($503-$1,601) | **+$572** ($2-$1,067) | +$51 (-$122 to +$472) |
| Builder 50K, Zlarior + ATLAS + BLITZ | $2,242 | $1,443 | $34 |
| Builder 25K, today: Zlarior alone / ATLAS alone | $388 / $650 | $300 / $293 | -$12 / -$4 |
| Builder 25K, best combo (Zlarior + ATLAS + BLITZ) | $1,065 | $495 | -$9 |
| Rapid EOD 25K, Zlarior + ATLAS (the preset built for it) | $2,146 | $617 | -$19 |
| Rapid EOD 25K, best combo (+ BLITZ, lane sizes) | $2,148 | $1,087 | -$9 |
| Builder 50K eval: pass in 60 days / median days / fail - Zlarior alone | 88% / 9 / 9% | 84% / 10 / 12% | 30% / 13 / 56% |
| ... Zlarior + ATLAS | 91% / **5** / 9% | 87% / **7** / 13% | 32% / 4 / 68% |
| ... failed inside 2 weeks: alone / + ATLAS | 0.1% / 4.0% | 0.1% / 2.1% | 0.5% / **34%** |
| Builder 50K funded: first payout within 30 days - alone / + ATLAS | 58% / 90% | 53% / 74% | 8% / 20% |

In plain words:
- **More money and faster:** Zlarior + ATLAS on the 50K passes in about a week instead of two, the funded account pays
  within 30 trading days 3 times in 4 instead of half the time, and the 6 months pay about +$570 a month more in a
  Jul-Oct-like market.
- **It is ATLAS's edge, not luck:** the same test with ATLAS's edge set to zero (same trades, same times, same swings)
  makes LESS than Zlarior alone ($388 / $529 a month). More trades alone do not pay.
- **The price:** more evals die inside 2 weeks (2-4% instead of ~0% in 2026; 34% in a 2021-25-like market), so you buy
  more evals ($91.80 each, already taken off the $ above). In 2021-25 it is better on average but worse in 65 of 100 runs,
  and in 2022 alone (Zlarior's good year) it made $113 a month LESS than Zlarior alone.
- **BLITZ burns the shared room:** at its own size it risks up to $2,100 on one trade on a 50K and doubles the eval fails
  (22-25%). With small "lane" sizes it is safer but no longer beats today in every period.
- **Which account:** the **Builder 50K**. It gives $21.8 of drawdown room per $1 of fee (25K $15.9, Rapid EOD 25K
  $10.3), 40 micros, and no best-day rule in the eval (one good day passes). The Rapid EOD 25K's 30% best-day + 4-day
  rule keeps its eval at 25-31 days even with 3 bots, and its funded account is stuck or lost in 18-41% of 6-month runs.
  The Builder 25K earns about half of the 50K for $28.80 less.
- **2021-25 stays about $0 for everything** (-$88 to +$66 a month across every main row). No combo creates an edge that is not there.

Next (paper only, nothing changed):
1. Decide on the card "Zlarior's 50K: ATLAS trades it too" (Board / ZEUS page).
2. On yes: the lead builds the one-position first-in rule on Zlarior's account and Sim-tests it before you arm anything.
3. Re-check after November: `/home/user/heavy.sh python -X utf8 tools/money/combo_account.py study`

## 1. The three plain answers

1. **Does trading more strategies on one account make more money a month and pass faster, or burn the room faster?**
   Both, depending on the pair. Zlarior + ATLAS: more money in all three periods, passes in ~5-7 days instead of 9-10,
   but more evals die early (bought back, and still ahead after the fees). Anything with BLITZ at its own size: the room
   burns - 2x the eval fails, a single trade can risk the whole $2,000 max loss after a green day. BLITZ at a small lane
   size: safe but only adds money in some periods. ATLAS + BLITZ without Zlarior also beats Zlarior alone on the 50K, but
   by little in Jul-Oct (+$147) and with 29-31% eval fails.
2. **Builder 25K or 50K, or a Rapid EOD 25K?** The **Builder 50K**. Per account it earns about 2x the 25K (same bots,
   2x the room, 2x the micros) for $28.80 more. The Rapid EOD 25K matches the 50K only in Jan-Jun; in Jul-Oct it makes
   about half ($617-$1,087 vs $1,286-$1,443), its eval needs 25-31 trading days (the 30% best-day rule + 4 days), and its
   funded account is stuck or lost in 18-41% of runs (small $1,000 room, sizes follow the room).
3. **Is it a 2026-only fluke?** For Zlarior + ATLAS on the 50K, no: it is ahead in 2021-25 too (+$51 a month, > 2
   standard errors) and in 3 of the 4 years 2022-25 - but 2021-25 is ~$0 for everything, and in 2022 it is behind.


## 2. How it was tested (fixed and committed before the first result: commit 4e682267)

- **Bots, as they are today, nothing re-tuned** (the repo's own stored trades, CME NQ1! futures bars only):
  - Zlarior (LIT): the 120 live-loop trades of 2026 (1m fills) + 511 of 2021-25 (5m) - `tools/account4_sim.load()`.
  - ATLAS: the raw EMA / MACD / S-R member trades (`tools/second_mix.units()`) with ATLAS's own rules (one position,
    max 2 a day). Not the version already cut around Zlarior: on one account the account rule below does that.
  - BLITZ: today's rule alone (`tools/blitz_review.sim`, engine/blitz VERSION 2 without account-C blocking), 2026 on 1m,
    2021-25 on 5m, with its later-break size flag.
  - Post-close follow (the parked lead, `tools/third_strategy` cell pcm_k5_follow_or15_r2_x0925): sensitivity rows only.
  - Costs: $1.90 a micro round trip + 1 tick on every market entry and every stop / market exit (limit entries and
    targets at the limit price). Sensitivity: +1 more tick on the entry AND the exit of every trade.
- **One account = one net NQ position.** Main rule "first-in": while any trade is open, every later signal (either
  side) is skipped. Sensitivity "adds": a same-side signal is added (micros capped at the plan's max together, sized from
  the room left after the open trade's full stop-out; open losses added worst-on-worst); the opposite side is skipped.
- **One shared room** (balance + today's closed P&L - the trailing floor), capped by the plan's max micros:
  - "own" (main): every bot keeps its live size rule on this plan's numbers - Zlarior's two_week (room_f 0.4, kept to
    session 80; funded 60% of the room, <= $1,500 / $750, a winner <= $2,000 / $1,000), ATLAS = `engine/account_b.qty` /
    `funded_qty` (need size, zombie last bullet, soft-day guard), BLITZ = `engine/account_c.qty`'s rule (40% of the room,
    the full room from session 5, <= $600, later break x0.5 / x1.75; funded 10%, <= $150, +$400 day stop; x2 on a 50K).
  - "lanes": the rule `engine/rapid.py` built for ONE account: the first bot (Zlarior > ATLAS > BLITZ) keeps its own size,
    every other bot risks min($cap, 30% of the room, the soft day left): ATLAS $250, BLITZ $150, post-close $125 on a 25K,
    x2 on a 50K.
  - Rapid EOD evals: the fleet's 30% best-day size guard on every trade.
- **Accounts** (`research/lit/mffu_rules.json`, `research/props/firm_rules.json`, `engine/rapid.PLANS`), the owner's CLUB
  prices: Builder 50K $91.80, Builder 25K $63, Rapid EOD 25K $97.20, Rapid EOD 50K $165 (reference). Eval target, EOD
  trailing max loss (open losses count, locks at +$100), soft daily loss, max micros, 30% best day + 4 days on the Rapid,
  16:10 flat (every bot is out by 15:55), Tier-1 news flat -2 / +2 min on the funded Rapid; funded buffer, min / max
  payout, 50% best day + 2 days a cycle + 48 h wait on the Builder, daily payouts above buffer + the bot's keep on the
  Rapid, 80% / 90% split, 5 Builder payouts. A funded account under its bots' stop-trading room is counted as lost (the
  bot stands down; a new eval is bought).
- **Monte Carlo:** whole days drawn with replacement from each period (a day keeps all its trades together), the same
  2,000 paths x 126 sessions (6 months) for every row: the account slot (eval -> 2 sessions paperwork -> funded -> lost /
  5 payouts -> buy the next eval; $ a month after every eval fee) and, separately, 2,000 x 126 from the first funded
  session. Eval numbers = the first eval of each slot path.
- **Parity:** the simulator reproduces the repo's checked ones on the same paths with 0 differences: `account4_sim.Ev`
  (Zlarior, Builder 50K eval), `uprisk.Funded` (Builder 50K / 25K funded), `rapid_levers.Rapid` (Rapid 25K funded),
  `rapid_levers.Ev` (Rapid 25K eval with the 30% guard), and the cached `engine/account_b` sizing
  (`python -X utf8 tools/money/combo_account.py check`).

## 3. Results (H1 = Jan-Jun 2026, H2 = Jul-Oct 16 2026, 21-25 = 2021-11 .. 2025)

Every $ a month below is the 6-month account slot after every eval fee (re-bought on a fail), your share after MFFU's split; brackets = 10% / 90% of the 2,000 runs. Eval columns: pass within 60 trading days, median days to pass (25-75%), fail within 60. Funded: first payout within 30 / 60 trading days of funding, account lost or stuck within 6 months. "own" = each bot's live size, "lanes" = engine/rapid's one-account lane sizes.

### A. The trades themselves (real days in order, $250 a trade, one position first-in, costs in)

| Combo | trades/wk H1 / H2 / 21-25 | win % | PF | net $ | $/month | max DD |
|---|---|---|---|---|---|---|
| Z | 3.12 / 2.56 / 2.37 | 58.8 / 50.0 / 53.6 | 3.71 / 3.0 / 1.02 | $14,406 / $6,615 / $908 | $2,363 / $1,781 / $18 | -$1,353 / -$902 / -$9,113 |
| A | 4.18 / 3.21 / 4.93 | 53.3 / 54.0 / 36.9 | 3.06 / 2.17 / 1.12 | $20,282 / $4,620 / $16,521 | $3,328 / $1,244 / $322 | -$1,062 / -$1,192 / -$10,364 |
| B | 8.63 / 6.99 / 8.68 | 55.7 / 55.0 / 50.3 | 1.51 / 1.82 / 1.05 | $6,328 / $4,181 / $6,429 | $1,038 / $1,126 / $125 | -$1,264 / -$983 / -$7,544 |
| Z+A | 6.05 / 5.06 / 6.49 | 56.1 / 53.2 / 41.5 | 3.3 / 2.58 / 1.04 | $28,826 / $9,937 / $7,374 | $4,729 / $2,675 / $144 | -$1,218 / -$1,052 / -$16,332 |
| Z+B | 11.29 / 9.49 / 10.8 | 56.7 / 53.4 / 51.0 | 2.27 / 2.27 / 1.04 | $21,054 / $10,718 / $7,468 | $3,454 / $2,886 / $146 | -$2,292 / -$1,146 / -$10,623 |
| A+B | 12.73 / 9.94 / 13.22 | 54.9 / 55.5 / 45.2 | 2.2 / 2.01 / 1.07 | $26,546 / $8,789 / $20,121 | $4,355 / $2,366 / $392 | -$1,167 / -$1,357 / -$15,741 |
| Z+A+B | 14.26 / 11.73 / 14.57 | 55.9 / 54.6 / 46.3 | 2.46 / 2.27 / 1.04 | $35,178 / $14,029 / $11,322 | $5,771 / $3,777 / $221 | -$1,408 / -$1,015 / -$20,372 |
| Z+A+P | 7.23 / 6.47 / 7.53 | 53.0 / 50.5 / 41.3 | 2.9 / 2.2 / 1.06 | $30,667 / $10,843 / $12,223 | $5,031 / $2,919 / $238 | -$1,213 / -$1,494 / -$11,725 |
| Z+A+B+P | 15.43 / 13.14 / 15.6 | 54.4 / 53.2 / 45.9 | 2.34 / 2.08 / 1.05 | $37,019 / $14,935 / $16,170 | $6,073 / $4,021 / $315 | -$1,213 / -$1,494 / -$11,808 |

### Builder 50K ($91.80)

| Row | $/month after fees, H1 / H2 / 21-25 (10-90% of paths) | lose money in 6 mo | eval pass in 60 / median days (25-75%) / fail | funded: 1st payout <= 30 / 60 days, lost or stuck |
|---|---|---|---|---|
| Z **(today)** | $827 ($251..$1,303) / $714 ($208..$1,303) / -$7 (-$61..$219) | 4.2% / 8.3% / 88.3% | 88.0%, 9.0 (3-20), 9.2% / 83.5%, 10.0 (4-22), 11.6% / 29.6%, 13.0 (6-28), 55.6% | 58.4/88.2%, 3.5% / 53.4/81.3%, 7.2% / 8.2/16.5%, 78.0% |
| A | $1,385 ($785..$2,058) / $622 (-$15..$1,287) / $61 (-$138..$457) | 0.3% / 13.3% / 61.0% | 88.4%, 7.0 (3-13), 11.4% / 79.9%, 12.0 (6-24), 15.1% / 37.1%, 5.0 (2-11), 62.9% | 78.7/94.0%, 5.8% / 45.5/75.3%, 11.8% / 20.8/24.4%, 93.1% |
| B | $333 (-$46..$744) / $268 (-$46..$709) / -$64 (-$155..-$15) | 22.9% / 32.1% / 93.5% | 41.5%, 5.0 (2-9), 58.5% / 53.9%, 6.0 (3-11), 46.1% / 22.9%, 5.0 (2-8), 77.1% | 7.4/39.4%, 3.5% / 4.2/28.6%, 5.2% / 0.4/2.8%, 49.2% |
| Z+A (own) | $1,888 ($1,287..$2,605) / $1,286 ($751..$1,836) / $44 (-$153..$457) | 0.0% / 1.1% / 61.8% | 90.7%, 5.0 (2-10), 9.2% / 86.9%, 7.0 (3-14), 12.5% / 32.4%, 4.0 (2-9), 67.6% | 90.2/96.7%, 3.8% / 74.3/92.1%, 7.8% / 19.5/22.6%, 94.5% |
| Z+A (lanes) | $1,479 ($1,036..$2,103) / $1,166 ($518..$1,790) / -$23 (-$122..$205) | 0.2% / 2.4% / 81.5% | 94.0%, 6.0 (3-13), 5.8% / 86.2%, 8.0 (4-16), 12.2% / 27.1%, 5.0 (2-11), 72.8% | 83.3/96.1%, 3.2% / 72.0/89.2%, 7.2% / 12.2/16.3%, 91.8% |
| Z+B (own) | $1,213 ($727..$1,785) / $1,073 ($487..$1,553) / -$7 (-$122..$221) | 0.7% / 2.5% / 79.6% | 72.8%, 5.0 (2-9), 26.8% / 71.9%, 4.0 (2-9), 27.4% / 25.6%, 4.0 (2-8), 73.9% | 75.8/95.8%, 2.5% / 67.5/91.4%, 4.9% / 10.1/19.9%, 82.7% |
| Z+B (lanes) | $1,118 ($503..$1,569) / $1,095 ($503..$1,562) / $5 (-$76..$221) | 2.2% / 1.9% / 83.2% | 88.3%, 8.0 (3-16), 10.3% / 88.5%, 10.0 (4-18), 9.2% / 31.8%, 12.0 (5-23), 61.9% | 72.2/91.5%, 7.4% / 72.4/92.5%, 4.8% / 11.6/19.4%, 86.0% |
| A+B (own) | $1,728 ($1,242..$2,369) / $861 ($221..$1,303) / $62 (-$184..$472) | 0.0% / 5.5% / 55.7% | 71.0%, 4.0 (2-7), 29.0% / 68.9%, 6.0 (3-11), 31.0% / 29.7%, 3.0 (2-6), 70.3% | 86.6/96.2%, 5.0% / 52.6/81.8%, 11.9% / 21.2/24.4%, 93.7% |
| A+B (lanes) | $1,645 ($1,051..$2,365) / $875 ($251..$1,303) / $66 (-$138..$472) | 0.1% / 4.4% / 59.8% | 87.4%, 6.0 (3-12), 12.6% / 86.3%, 12.0 (6-21), 12.2% / 36.5%, 5.0 (2-10), 63.5% | 83.0/92.5%, 9.2% / 58.6/86.2%, 9.7% / 21.2/23.8%, 92.4% |
| Z+A+B (own) | $2,242 ($1,524..$2,855) / $1,443 ($989..$2,087) / $34 (-$214..$453) | 0.0% / 0.2% / 56.7% | 78.3%, 4.0 (2-7), 21.6% / 75.2%, 4.0 (2-8), 24.8% / 28.2%, 3.0 (2-6), 71.8% | 94.9/98.0%, 2.5% / 78.2/93.2%, 7.2% / 19.8/22.3%, 94.2% |
| Z+A+B (lanes) | $1,730 ($1,269..$2,369) / $1,404 ($785..$2,087) / -$11 (-$138..$221) | 0.0% / 0.8% / 76.9% | 93.2%, 6.0 (3-11), 6.7% / 89.5%, 8.0 (4-14), 9.9% / 27.4%, 5.0 (2-10), 72.5% | 87.5/95.5%, 4.7% / 80.9/93.3%, 6.3% / 12.8/16.4%, 91.3% |

### Builder 25K ($63.00)

| Row | $/month after fees, H1 / H2 / 21-25 (10-90% of paths) | lose money in 6 mo | eval pass in 60 / median days (25-75%) / fail | funded: 1st payout <= 30 / 60 days, lost or stuck |
|---|---|---|---|---|
| Z **(today)** | $388 ($111..$646) / $300 (-$21..$624) / -$12 (-$32..-$10) | 7.5% / 18.3% / 91.2% | 87.8%, 9.0 (3-21), 1.3% / 80.4%, 10.0 (4-22), 2.0% / 27.4%, 13.0 (5-27), 30.4% | 57.6/87.0%, 8.6% / 48.0/78.0%, 15.9% / 7.2/15.5%, 81.7% |
| A **(today)** | $650 ($389..$907) / $293 (-$21..$523) / -$4 (-$116..$204) | 0.3% / 11.4% / 59.8% | 80.5%, 6.0 (2-11), 19.4% / 75.2%, 12.0 (6-22), 23.2% / 33.0%, 5.0 (2-10), 67.0% | 76.3/93.1%, 8.8% / 43.0/74.0%, 19.5% / 18.8/22.1%, 95.1% |
| B | $242 (-$42..$517) / $63 (-$52..$242) / -$55 (-$126..$62) | 15.0% / 51.1% / 88.0% | 40.4%, 5.0 (2-9), 59.6% / 54.5%, 6.0 (3-10), 45.5% / 23.1%, 4.0 (2-7), 76.8% | 23.4/59.1%, 31.8% / 4.2/21.9%, 58.9% / 0.8/4.5%, 77.5% |
| Z+A (own) | $889 ($615..$1,291) / $534 (-$10..$883) / -$6 (-$52..$102) | 1.4% / 10.2% / 80.9% | 90.8%, 5.0 (2-11), 4.7% / 82.5%, 7.0 (3-14), 3.1% / 31.5%, 4.0 (2-9), 51.0% | 89.2/94.4%, 7.2% / 71.9/86.9%, 18.0% / 17.6/20.3%, 96.0% |
| Z+A (lanes) | $682 ($390..$1,030) / $429 (-$21..$646) / -$15 (-$52..$82) | 1.9% / 14.4% / 89.0% | 93.7%, 7.0 (3-14), 1.2% / 80.6%, 9.0 (4-16), 1.8% / 26.6%, 5.0 (2-12), 49.0% | 79.7/91.0%, 8.9% / 63.7/82.0%, 20.6% / 11.5/15.6%, 92.4% |
| Z+B (own) | $632 ($235..$1,014) / $375 (-$21..$646) / -$16 (-$63..$91) | 4.3% / 22.4% / 84.0% | 73.3%, 4.0 (2-8), 19.4% / 67.7%, 4.0 (2-8), 10.3% / 25.4%, 4.0 (2-7), 62.5% | 81.8/93.0%, 9.6% / 57.8/80.2%, 21.6% / 10.5/19.8%, 87.8% |
| Z+B (lanes) | $417 (-$10..$646) / $472 ($94..$646) / -$7 (-$42..$93) | 10.1% / 8.8% / 87.8% | 85.0%, 9.0 (3-19), 1.9% / 87.2%, 10.0 (4-19), 1.1% / 29.2%, 12.0 (5-23), 38.6% | 62.6/83.9%, 16.7% / 65.8/90.2%, 9.6% / 10.2/19.7%, 86.8% |
| A+B (own) | $897 ($604..$1,273) / $353 ($79..$635) / -$20 (-$178..$214) | 0.1% / 6.3% / 62.8% | 63.7%, 3.0 (2-6), 36.3% / 59.2%, 5.0 (2-8), 40.8% / 26.1%, 3.0 (1-5), 73.9% | 85.8/91.0%, 12.5% / 45.2/69.7%, 34.0% / 21.1/23.4%, 95.2% |
| A+B (lanes) | $686 ($390..$1,005) / $460 ($217..$646) / -$3 (-$126..$214) | 0.2% / 2.1% / 58.9% | 77.2%, 6.0 (2-10), 22.8% / 83.2%, 11.0 (6-20), 16.4% / 33.0%, 5.0 (2-8), 67.0% | 76.2/88.0%, 15.6% / 62.0/88.2%, 10.7% / 19.5/21.8%, 94.7% |
| Z+A+B (own) | $1,065 ($614..$1,523) / $495 (-$21..$893) / -$9 (-$74..$91) | 1.8% / 17.6% / 79.3% | 80.0%, 3.0 (1-7), 13.8% / 68.4%, 4.0 (2-8), 11.6% / 27.5%, 3.0 (1-6), 61.1% | 92.8/94.0%, 8.1% / 70.8/81.8%, 23.8% / 18.7/20.3%, 95.8% |
| Z+A+B (lanes) | $684 ($379..$1,046) / $562 ($110..$897) / -$12 (-$52..$94) | 3.0% / 8.2% / 87.1% | 92.1%, 7.0 (3-13), 1.9% / 86.4%, 8.0 (4-15), 1.7% / 26.3%, 5.0 (2-10), 51.2% | 80.2/88.7%, 12.6% / 74.6/88.7%, 13.3% / 12.4/15.5%, 92.0% |

### Rapid EOD 25K ($97.20)

| Row | $/month after fees, H1 / H2 / 21-25 (10-90% of paths) | lose money in 6 mo | eval pass in 60 / median days (25-75%) / fail | funded: 1st payout <= 30 / 60 days, lost or stuck |
|---|---|---|---|---|
| Z | $311 (-$16..$907) / $145 (-$32..$529) / -$21 (-$32..-$16) | 40.6% / 56.5% / 99.3% | 33.8%, 46.0 (36-54), 0.0% / 37.2%, 44.0 (33-52), 0.1% / 2.1%, 45.0 (36-53), 2.5% | 53.7/86.6%, 7.7% / 30.3/61.6%, 27.9% / 5.2/13.6%, 78.7% |
| A | $935 (-$16..$1,760) / $232 (-$32..$698) / -$33 (-$81..-$32) | 11.8% / 42.6% / 91.3% | 71.0%, 35.0 (26-46), 5.2% / 55.4%, 38.0 (28-49), 6.1% / 17.9%, 34.0 (24-47), 66.0% | 73.2/92.8%, 11.7% / 28.1/62.6%, 27.6% / 16.6/21.0%, 99.0% |
| B | $71 (-$65..$351) / $3 (-$49..$115) / -$55 (-$97..-$16) | 62.9% / 80.9% / 97.1% | 32.5%, 37.0 (27-48), 47.9% / 47.9%, 34.0 (26-45), 32.5% / 18.4%, 34.0 (26-45), 72.0% | 15.9/52.5%, 26.6% / 2.3/17.6%, 48.8% / 0.3/2.9%, 75.4% |
| Z+A (own) | $1,830 ($881..$2,705) / $643 (-$32..$1,372) / -$21 (-$49..-$32) | 1.2% / 18.9% / 93.4% | 93.8%, 28.0 (20-37), 0.1% / 79.5%, 31.0 (22-43), 1.0% / 17.1%, 33.0 (22-44), 36.6% | 88.2/94.9%, 11.4% / 55.1/78.5%, 34.9% / 17.4/19.9%, 99.6% |
| Z+A (lanes) **(today)** | $2,146 ($825..$3,410) / $617 (-$32..$1,436) / -$19 (-$49..-$16) | 1.9% / 23.6% / 94.3% | 93.2%, 28.0 (20-37), 0.0% / 78.5%, 31.0 (22-43), 0.2% / 15.5%, 33.0 (22-45), 31.2% | 85.7/92.7%, 18.4% / 51.6/73.0%, 41.1% / 17.9/20.4%, 99.5% |
| Z+B (own) | $974 (-$32..$1,931) / $452 (-$32..$1,065) / -$25 (-$65..-$16) | 18.3% / 25.9% / 93.7% | 66.6%, 29.0 (20-41), 3.7% / 80.4%, 26.0 (19-36), 2.2% / 19.1%, 31.0 (22-43), 40.0% | 79.7/93.9%, 10.2% / 39.5/67.5%, 37.2% / 7.8/17.7%, 88.9% |
| Z+B (lanes) | $508 (-$32..$1,291) / $603 (-$16..$1,175) / -$21 (-$49..-$16) | 31.8% / 13.7% / 95.1% | 53.1%, 35.0 (25-47), 0.7% / 87.1%, 31.0 (22-41), 0.3% / 16.1%, 40.0 (28-51), 22.4% | 61.0/84.4%, 22.0% / 49.1/80.8%, 16.8% / 8.3/18.2%, 88.1% |
| A+B (own) | $1,550 ($400..$2,555) / $335 (-$49..$844) / -$39 (-$130..$145) | 5.0% / 30.8% / 83.2% | 65.0%, 24.0 (17-33), 32.6% / 69.0%, 29.0 (20-39), 24.6% / 21.4%, 23.0 (16-32), 77.5% | 85.5/92.2%, 17.8% / 32.6/63.1%, 43.1% / 19.1/22.1%, 99.4% |
| A+B (lanes) | $1,055 (-$16..$1,971) / $637 (-$16..$1,268) / -$30 (-$97..$102) | 10.3% / 13.7% / 86.0% | 71.2%, 30.0 (21-41), 16.2% / 81.0%, 31.0 (22-42), 6.8% / 22.9%, 26.0 (18-38), 72.5% | 74.5/88.0%, 24.4% / 51.9/83.0%, 16.1% / 18.9/21.8%, 99.2% |
| Z+A+B (own) | $2,312 ($880..$3,483) / $687 (-$32..$1,440) / -$19 (-$65..-$16) | 4.0% / 19.1% / 90.7% | 85.2%, 20.0 (14-30), 5.1% / 82.7%, 23.0 (16-32), 3.7% / 21.4%, 23.0 (15-31), 53.0% | 93.2/94.9%, 14.1% / 55.1/73.3%, 47.8% / 17.9/19.8%, 99.8% |
| Z+A+B (lanes) | $2,148 ($665..$3,555) / $1,087 ($71..$1,998) / -$9 (-$65..-$16) | 3.5% / 9.2% / 91.2% | 90.0%, 25.0 (17-35), 0.5% / 90.2%, 25.0 (17-34), 0.2% / 20.8%, 27.0 (17-39), 38.6% | 84.9/90.6%, 27.1% / 66.8/82.7%, 29.8% / 18.4/20.8%, 99.7% |

### Rapid EOD 50K (reference) ($165.00)

| Row | $/month after fees, H1 / H2 / 21-25 (10-90% of paths) | lose money in 6 mo | eval pass in 60 / median days (25-75%) / fail | funded: 1st payout <= 30 / 60 days, lost or stuck |
|---|---|---|---|---|
| Z | $1,001 (-$28..$2,287) / $677 (-$28..$1,734) / -$38 (-$55..-$28) | 23.1% / 29.0% / 98.3% | 53.1%, 41.0 (32-50), 0.1% / 64.0%, 38.0 (29-48), 0.7% / 4.0%, 46.0 (34-54), 13.0% | 61.6/89.8%, 3.2% / 46.6/72.1%, 15.2% / 9.7/18.9%, 76.5% |
| A | $2,885 ($1,060..$4,618) / $606 (-$55..$1,633) / -$15 (-$138..$202) | 1.9% / 34.8% / 86.2% | 93.1%, 24.0 (17-34), 2.1% / 65.0%, 35.0 (25-46), 3.0% / 22.4%, 30.0 (21-42), 62.7% | 81.0/94.8%, 9.1% / 35.5/67.3%, 16.6% / 22.2/26.1%, 99.2% |
| B | $153 (-$82..$573) / $101 (-$82..$476) / -$88 (-$165..-$28) | 51.3% / 61.2% / 97.3% | 51.3%, 32.0 (23-42), 38.1% / 52.4%, 32.0 (23-43), 34.7% / 21.8%, 32.0 (23-42), 72.0% | 7.2/38.9%, 3.1% / 4.5/29.7%, 4.0% / 0.4/2.6%, 47.6% |
| Z+A (own) | $4,409 ($2,600..$6,212) / $1,954 ($411..$3,531) / -$22 (-$138..$222) | 0.2% / 5.5% / 85.0% | 98.4%, 19.0 (14-26), 0.7% / 92.0%, 24.0 (17-34), 2.8% / 21.4%, 28.0 (18-38), 70.5% | 92.0/97.4%, 6.1% / 66.8/87.4%, 19.4% / 23.1/25.2%, 99.7% |
| Z+A (lanes) **(today)** | $5,457 ($2,835..$7,991) / $2,214 ($317..$4,123) / -$5 (-$138..$218) | 0.2% / 6.5% / 86.7% | 98.2%, 20.0 (14-27), 0.3% / 91.2%, 25.0 (17-35), 2.4% / 19.8%, 29.0 (19-39), 69.0% | 91.2/97.2%, 8.4% / 68.5/85.5%, 21.5% / 22.6/25.1%, 99.5% |
| Z+B (own) | $2,313 ($786..$3,851) / $1,574 ($156..$2,858) / -$29 (-$138..$87) | 3.7% / 7.7% / 87.8% | 81.5%, 24.0 (17-34), 11.4% / 85.0%, 23.0 (16-32), 10.1% / 23.7%, 28.0 (20-38), 65.0% | 78.0/96.3%, 2.6% / 61.2/86.3%, 9.5% / 11.4/21.7%, 82.9% |
| Z+B (lanes) | $2,096 ($337..$3,704) / $1,787 ($341..$3,126) / -$26 (-$110..-$28) | 6.3% / 5.8% / 91.3% | 82.9%, 28.0 (20-39), 4.3% / 91.5%, 26.0 (18-36), 2.0% / 18.9%, 35.0 (24-45), 50.1% | 74.6/92.3%, 10.4% / 68.0/89.5%, 9.6% / 15.2/23.9%, 89.4% |
| A+B (own) | $3,830 ($1,974..$5,684) / $1,047 (-$55..$2,234) / $8 (-$192..$472) | 0.6% / 16.5% / 77.8% | 85.2%, 17.0 (12-25), 14.1% / 81.0%, 25.0 (17-35), 12.7% / 27.0%, 20.0 (14-29), 71.5% | 88.7/96.8%, 8.3% / 45.0/75.8%, 17.4% / 23.0/26.1%, 99.2% |
| A+B (lanes) | $3,675 ($1,702..$5,621) / $1,428 (-$28..$2,823) / $13 (-$165..$430) | 0.8% / 11.0% / 79.8% | 93.8%, 19.0 (13-27), 4.6% / 84.7%, 28.0 (20-39), 5.2% / 27.0%, 24.0 (16-35), 68.5% | 85.7/93.2%, 17.9% / 58.6/84.5%, 13.8% / 25.0/26.5%, 99.5% |
| Z+A+B (own) | $5,380 ($3,522..$7,282) / $2,394 ($746..$3,961) / -$4 (-$220..$448) | 0.1% / 2.7% / 78.4% | 92.7%, 14.0 (10-21), 7.0% / 92.2%, 18.0 (13-26), 7.0% / 24.8%, 19.0 (13-26), 74.2% | 96.2/98.7%, 4.8% / 71.9/89.6%, 16.9% / 22.6/25.1%, 99.7% |
| Z+A+B (lanes) | $6,370 ($3,583..$9,121) / $3,298 ($1,195..$5,309) / $9 (-$165..$347) | 0.1% / 1.9% / 82.2% | 98.4%, 15.0 (11-22), 1.2% / 95.5%, 21.0 (14-29), 2.7% / 23.4%, 21.0 (15-32), 73.4% | 92.2/96.5%, 12.3% / 79.0/90.5%, 17.1% / 22.8/24.6%, 99.8% |

### Sensitivities ($/month after fees, H1 / H2 / 21-25)

| Account | Row | main | +1 tick | same-side adds |
|---|---|---|---|---|
| Builder 50K | Z | $827 / $714 / -$7 | $793 / $696 / -$11 | - |
| Builder 50K | A | $1,385 / $622 / $61 | $1,358 / $589 / $41 | - |
| Builder 50K | B | $333 / $268 / -$64 | $302 / $241 / -$78 | - |
| Builder 50K | Z+A (own) | $1,888 / $1,286 / $44 | $1,840 / $1,256 / $26 | $1,745 / $1,456 / $34 |
| Builder 50K | Z+A (lanes) | $1,479 / $1,166 / -$23 | $1,438 / $1,123 / -$33 | $1,395 / $1,327 / -$29 |
| Builder 50K | Z+B (own) | $1,213 / $1,073 / -$7 | $1,170 / $1,041 / -$21 | $1,218 / $1,079 / -$9 |
| Builder 50K | Z+B (lanes) | $1,118 / $1,095 / $5 | $1,073 / $1,047 / -$11 | $1,130 / $1,100 / $5 |
| Builder 50K | A+B (own) | $1,728 / $861 / $62 | $1,695 / $817 / $27 | $1,723 / $861 / $64 |
| Builder 50K | A+B (lanes) | $1,645 / $875 / $66 | $1,590 / $834 / $35 | $1,642 / $875 / $66 |
| Builder 50K | Z+A+B (own) | $2,242 / $1,443 / $34 | $2,194 / $1,403 / $4 | $2,111 / $1,612 / $34 |
| Builder 50K | Z+A+B (lanes) | $1,730 / $1,404 / -$11 | $1,670 / $1,348 / -$30 | $1,628 / $1,566 / -$15 |
| Builder 25K | Z | $388 / $300 / -$12 | $368 / $290 / -$14 | - |
| Builder 25K | A | $650 / $293 / -$4 | $636 / $279 / -$17 | - |
| Builder 25K | B | $242 / $63 / -$55 | $229 / $51 / -$66 | - |
| Builder 25K | Z+A (own) | $889 / $534 / -$6 | $861 / $515 / -$11 | $839 / $590 / -$9 |
| Builder 25K | Z+A (lanes) | $682 / $429 / -$15 | $666 / $406 / -$19 | $644 / $508 / -$17 |
| Builder 25K | Z+B (own) | $632 / $375 / -$16 | $606 / $361 / -$23 | $632 / $377 / -$16 |
| Builder 25K | Z+B (lanes) | $417 / $472 / -$7 | $395 / $454 / -$13 | $424 / $475 / -$8 |
| Builder 25K | A+B (own) | $897 / $353 / -$20 | $878 / $332 / -$41 | $894 / $353 / -$18 |
| Builder 25K | A+B (lanes) | $686 / $460 / -$3 | $664 / $442 / -$22 | $686 / $460 / -$3 |
| Builder 25K | Z+A+B (own) | $1,065 / $495 / -$9 | $1,021 / $474 / -$17 | $1,018 / $545 / -$11 |
| Builder 25K | Z+A+B (lanes) | $684 / $562 / -$12 | $657 / $535 / -$18 | $645 / $643 / -$12 |
| Rapid EOD 25K | Z | $311 / $145 / -$21 | $297 / $138 / -$22 | - |
| Rapid EOD 25K | A | $935 / $232 / -$33 | $900 / $218 / -$41 | - |
| Rapid EOD 25K | B | $71 / $3 / -$55 | $59 / -$3 / -$60 | - |
| Rapid EOD 25K | Z+A (own) | $1,830 / $643 / -$21 | $1,774 / $606 / -$25 | $2,052 / $495 / -$23 |
| Rapid EOD 25K | Z+A (lanes) | $2,146 / $617 / -$19 | $2,071 / $573 / -$22 | $2,524 / $720 / -$18 |
| Rapid EOD 25K | Z+B (own) | $974 / $452 / -$25 | $915 / $414 / -$29 | $970 / $456 / -$23 |
| Rapid EOD 25K | Z+B (lanes) | $508 / $603 / -$21 | $460 / $568 / -$25 | $507 / $610 / -$20 |
| Rapid EOD 25K | A+B (own) | $1,550 / $335 / -$39 | $1,492 / $303 / -$57 | $1,539 / $335 / -$39 |
| Rapid EOD 25K | A+B (lanes) | $1,055 / $637 / -$30 | $978 / $596 / -$44 | $1,055 / $637 / -$31 |
| Rapid EOD 25K | Z+A+B (own) | $2,312 / $687 / -$19 | $2,206 / $630 / -$29 | $2,571 / $778 / -$17 |
| Rapid EOD 25K | Z+A+B (lanes) | $2,148 / $1,087 / -$9 | $2,022 / $1,013 / -$20 | $2,540 / $1,259 / -$10 |
| Rapid EOD 50K (reference) | Z | $1,001 / $677 / -$38 | $960 / $653 / -$40 | - |
| Rapid EOD 50K (reference) | A | $2,885 / $606 / -$15 | $2,803 / $564 / -$34 | - |
| Rapid EOD 50K (reference) | B | $153 / $101 / -$88 | $123 / $82 / -$100 | - |
| Rapid EOD 50K (reference) | Z+A (own) | $4,409 / $1,954 / -$22 | $4,295 / $1,872 / -$38 | $3,210 / $1,749 / -$39 |
| Rapid EOD 50K (reference) | Z+A (lanes) | $5,457 / $2,214 / -$5 | $5,309 / $2,106 / -$30 | $6,185 / $2,499 / -$20 |
| Rapid EOD 50K (reference) | Z+B (own) | $2,313 / $1,574 / -$29 | $2,200 / $1,494 / -$46 | $2,303 / $1,594 / -$29 |
| Rapid EOD 50K (reference) | Z+B (lanes) | $2,096 / $1,787 / -$26 | $1,957 / $1,651 / -$44 | $2,114 / $1,810 / -$26 |
| Rapid EOD 50K (reference) | A+B (own) | $3,830 / $1,047 / $8 | $3,695 / $961 / -$32 | $3,807 / $1,047 / $3 |
| Rapid EOD 50K (reference) | A+B (lanes) | $3,675 / $1,428 / $13 | $3,516 / $1,324 / -$27 | $3,654 / $1,428 / $12 |
| Rapid EOD 50K (reference) | Z+A+B (own) | $5,380 / $2,394 / -$4 | $5,205 / $2,265 / -$46 | $6,011 / $2,773 / $0 |
| Rapid EOD 50K (reference) | Z+A+B (lanes) | $6,370 / $3,298 / $9 | $6,142 / $3,080 / -$24 | $7,278 / $3,681 / $13 |

### Zlarior eval, combo once funded; post-close lead added ($/month after fees H1 / H2 / 21-25; funded 1st payout <= 30 days)

| Account | Row | $/month | funded pay <= 30 d | eval fail in 60 |
|---|---|---|---|---|
| Builder 50K | Z eval, Z+A funded (own) | $1,627 / $1,146 / $11 | 90.2% / 74.3% / 19.5% | 9.2% / 11.6% / 55.6% |
| Builder 50K | Z eval, Z+A funded (lanes) | $1,333 / $1,080 / -$8 | 83.3% / 72.0% / 12.2% | 9.2% / 11.6% / 55.6% |
| Builder 50K | Z eval, Z+B funded (own) | $1,141 / $978 / $1 | 75.8% / 67.5% / 10.1% | 9.2% / 11.6% / 55.6% |
| Builder 50K | Z eval, Z+B funded (lanes) | $1,085 / $1,026 / $5 | 72.2% / 72.4% / 11.6% | 9.2% / 11.6% / 55.6% |
| Builder 50K | Z eval, Z+A+B funded (own) | $1,850 / $1,230 / $16 | 94.9% / 78.2% / 19.8% | 9.2% / 11.6% / 55.6% |
| Builder 50K | Z eval, Z+A+B funded (lanes) | $1,515 / $1,242 / -$5 | 87.5% / 80.9% / 12.8% | 9.2% / 11.6% / 55.6% |
| Builder 50K | Z+A+P (own) | $2,006 / $1,341 / $46 | 92.5% / 74.8% / 18.9% | 8.5% / 14.8% / 66.7% |
| Builder 50K | Z+A+P (lanes) | $1,569 / $1,190 / -$16 | 85.7% / 71.8% / 12.8% | 4.9% / 15.5% / 72.2% |
| Builder 50K | Z+A+B+P (own) | $2,338 / $1,489 / $42 | 95.4% / 77.8% / 19.1% | 21.1% / 27.4% / 70.5% |
| Builder 50K | Z+A+B+P (lanes) | $1,837 / $1,507 / -$10 | 89.5% / 81.4% / 12.9% | 5.8% / 12.0% / 71.9% |
| Builder 25K | Z eval, Z+A funded (own) | $766 / $485 / -$8 | 89.2% / 71.9% / 17.6% | 1.3% / 2.0% / 30.4% |
| Builder 25K | Z eval, Z+A funded (lanes) | $615 / $414 / -$11 | 79.7% / 63.7% / 11.5% | 1.3% / 2.0% / 30.4% |
| Builder 25K | Z eval, Z+B funded (own) | $607 / $381 / -$9 | 81.8% / 57.8% / 10.5% | 1.3% / 2.0% / 30.4% |
| Builder 25K | Z eval, Z+B funded (lanes) | $426 / $433 / -$8 | 62.6% / 65.8% / 10.2% | 1.3% / 2.0% / 30.4% |
| Builder 25K | Z eval, Z+A+B funded (own) | $919 / $484 / -$5 | 92.8% / 70.8% / 18.7% | 1.3% / 2.0% / 30.4% |
| Builder 25K | Z eval, Z+A+B funded (lanes) | $627 / $500 / -$11 | 80.2% / 74.6% / 12.4% | 1.3% / 2.0% / 30.4% |
| Builder 25K | Z+A+P (own) | $954 / $549 / -$5 | 91.5% / 73.3% / 18.2% | 3.2% / 4.0% / 58.2% |
| Builder 25K | Z+A+P (lanes) | $739 / $431 / -$17 | 83.8% / 65.8% / 12.1% | 1.0% / 2.2% / 57.5% |
| Builder 25K | Z+A+B+P (own) | $1,121 / $514 / -$9 | 93.5% / 73.4% / 18.4% | 13.4% / 11.9% / 65.7% |
| Builder 25K | Z+A+B+P (lanes) | $755 / $579 / -$13 | 83.5% / 76.7% / 12.3% | 1.1% / 1.4% / 58.8% |
| Rapid EOD 25K | Z eval, Z+A funded (own) | $810 / $329 / -$20 | 88.2% / 55.1% / 17.4% | 0.0% / 0.1% / 2.5% |
| Rapid EOD 25K | Z eval, Z+A funded (lanes) | $974 / $321 / -$19 | 85.7% / 51.6% / 17.9% | 0.0% / 0.1% / 2.5% |
| Rapid EOD 25K | Z eval, Z+B funded (own) | $554 / $212 / -$21 | 79.7% / 39.5% / 7.8% | 0.0% / 0.1% / 2.5% |
| Rapid EOD 25K | Z eval, Z+B funded (lanes) | $360 / $285 / -$21 | 61.0% / 49.1% / 8.3% | 0.0% / 0.1% / 2.5% |
| Rapid EOD 25K | Z eval, Z+A+B funded (own) | $1,039 / $316 / -$19 | 93.2% / 55.1% / 17.9% | 0.0% / 0.1% / 2.5% |
| Rapid EOD 25K | Z eval, Z+A+B funded (lanes) | $981 / $492 / -$18 | 84.9% / 66.8% / 18.4% | 0.0% / 0.1% / 2.5% |
| Rapid EOD 25K | Z+A+P (own) | $2,039 / $685 / -$18 | 90.7% / 59.0% / 17.9% | 0.1% / 2.0% / 42.8% |
| Rapid EOD 25K | Z+A+P (lanes) | $2,415 / $637 / -$13 | 88.2% / 54.5% / 18.4% | 0.1% / 0.6% / 39.0% |
| Rapid EOD 25K | Z+A+B+P (own) | $2,540 / $764 / -$21 | 93.9% / 59.8% / 18.1% | 3.5% / 5.0% / 58.9% |
| Rapid EOD 25K | Z+A+B+P (lanes) | $2,374 / $1,095 / -$6 | 87.0% / 67.8% / 18.3% | 0.1% / 0.5% / 47.7% |
| Rapid EOD 50K (reference) | Z eval, Z+A funded (own) | $2,449 / $1,314 / -$32 | 92.0% / 66.8% / 23.1% | 0.1% / 0.7% / 13.0% |
| Rapid EOD 50K (reference) | Z eval, Z+A funded (lanes) | $3,101 / $1,510 / -$28 | 91.2% / 68.5% / 22.6% | 0.1% / 0.7% / 13.0% |
| Rapid EOD 50K (reference) | Z eval, Z+B funded (own) | $1,464 / $1,086 / -$36 | 78.0% / 61.2% / 11.4% | 0.1% / 0.7% / 13.0% |
| Rapid EOD 50K (reference) | Z eval, Z+B funded (lanes) | $1,406 / $1,262 / -$35 | 74.6% / 68.0% / 15.2% | 0.1% / 0.7% / 13.0% |
| Rapid EOD 50K (reference) | Z eval, Z+A+B funded (own) | $2,899 / $1,481 / -$32 | 96.2% / 71.9% / 22.6% | 0.1% / 0.7% / 13.0% |
| Rapid EOD 50K (reference) | Z eval, Z+A+B funded (lanes) | $3,443 / $2,121 / -$29 | 92.2% / 79.0% / 22.8% | 0.1% / 0.7% / 13.0% |
| Rapid EOD 50K (reference) | Z+A+P (own) | $4,713 / $2,088 / -$16 | 94.2% / 69.5% / 23.4% | 0.7% / 6.8% / 69.5% |
| Rapid EOD 50K (reference) | Z+A+P (lanes) | $5,737 / $2,210 / $1 | 92.5% / 69.0% / 23.5% | 0.6% / 6.5% / 68.0% |
| Rapid EOD 50K (reference) | Z+A+B+P (own) | $5,570 / $2,512 / -$4 | 96.6% / 73.1% / 23.9% | 5.4% / 9.8% / 74.5% |
| Rapid EOD 50K (reference) | Z+A+B+P (lanes) | $6,643 / $3,284 / $15 | 93.2% / 79.2% / 23.2% | 1.4% / 5.9% / 73.3% |

### Verdict (pre-registered: above today's setup by > 2 SE in all three periods, 6-month loss chance not +5 pts, still above at +1 tick)

| Account | Row | gap vs today $/month H1 / H2 / 21-25 (2 SE) | beats today? |
|---|---|---|---|
| Builder 50K | Z+A (own) | +1,060 (21) / +572 (19) / +51 (12) | YES |
| Builder 50K | Z+A (lanes) | +652 (19) / +452 (19) / -15 (8) | no |
| Builder 50K | Z+B (own) | +386 (14) / +359 (15) / +1 (7) | no |
| Builder 50K | Z+B (lanes) | +291 (13) / +381 (14) / +12 (6) | no |
| Builder 50K | A+B (own) | +901 (28) / +147 (28) / +69 (14) | YES |
| Builder 50K | A+B (lanes) | +818 (27) / +161 (27) / +74 (13) | YES |
| Builder 50K | Z+A+B (own) | +1,415 (23) / +729 (20) / +42 (13) | YES |
| Builder 50K | Z+A+B (lanes) | +902 (21) / +689 (20) / -4 (9) | no |
| Builder 50K | Z eval, Z+A funded (own) | +800 (19) / +432 (16) / +18 (7) | YES |
| Builder 50K | Z eval, Z+A funded (lanes) | +506 (17) / +366 (16) / +0 (6) | no |
| Builder 50K | Z eval, Z+B funded (own) | +314 (11) / +264 (11) / +9 (4) | YES |
| Builder 50K | Z eval, Z+B funded (lanes) | +258 (12) / +312 (12) / +13 (5) | YES |
| Builder 50K | Z eval, Z+A+B funded (own) | +1,023 (22) / +516 (18) / +23 (8) | YES |
| Builder 50K | Z eval, Z+A+B funded (lanes) | +688 (19) / +527 (17) / +3 (6) | no |
| Builder 25K | Z+A (own) | +502 (13), +240 (11) / +234 (12), +240 (12) / +6 (4), -2 (6) | no |
| Builder 25K | Z+A (lanes) | +294 (10), +32 (9) / +130 (11), +136 (12) / -4 (3), -12 (6) | no |
| Builder 25K | Z+B (own) | +244 (11), -18 (15) / +75 (11), +82 (16) / -5 (3), -13 (7) | no |
| Builder 25K | Z+B (lanes) | +30 (7), -232 (14) / +172 (8), +178 (14) / +4 (3), -4 (7) | no |
| Builder 25K | A+B (own) | +509 (15), +247 (8) / +53 (14), +60 (8) / -8 (8), -16 (5) | no |
| Builder 25K | A+B (lanes) | +298 (13), +36 (6) / +160 (14), +167 (6) / +8 (7), +0 (4) | no |
| Builder 25K | Z+A+B (own) | +677 (17), +415 (16) / +195 (15), +202 (15) / +2 (5), -6 (6) | no |
| Builder 25K | Z+A+B (lanes) | +297 (11), +35 (11) / +262 (12), +269 (12) / +0 (4), -8 (6) | no |
| Builder 25K | Z eval, Z+A funded (own) | +378 (10), +116 (14) / +185 (9), +192 (13) / +4 (3), -4 (6) | no |
| Builder 25K | Z eval, Z+A funded (lanes) | +227 (9), -35 (12) / +114 (8), +120 (13) / +1 (3), -7 (6) | no |
| Builder 25K | Z eval, Z+B funded (own) | +219 (7), -43 (15) / +81 (6), +87 (15) / +3 (2), -5 (6) | no |
| Builder 25K | Z eval, Z+B funded (lanes) | +39 (5), -223 (14) / +133 (6), +139 (14) / +3 (2), -5 (6) | no |
| Builder 25K | Z eval, Z+A+B funded (own) | +532 (12), +270 (16) / +184 (9), +191 (14) / +7 (3), -1 (6) | no |
| Builder 25K | Z eval, Z+A+B funded (lanes) | +239 (9), -23 (12) / +200 (9), +207 (14) / +1 (3), -7 (6) | no |
| Rapid EOD 25K | Z+A (own) | -316 (22) / +26 (13) / -2 (4) | no |
| Rapid EOD 25K | Z+B (own) | -1,172 (48) / -165 (27) / -6 (5) | no |
| Rapid EOD 25K | Z+B (lanes) | -1,638 (43) / -14 (24) / -2 (5) | no |
| Rapid EOD 25K | A+B (own) | -595 (40) / -282 (25) / -20 (8) | no |
| Rapid EOD 25K | A+B (lanes) | -1,091 (36) / +20 (24) / -11 (7) | no |
| Rapid EOD 25K | Z+A+B (own) | +166 (39) / +70 (23) / +0 (6) | no |
| Rapid EOD 25K | Z+A+B (lanes) | +2 (30) / +470 (19) / +10 (5) | no |
| Rapid EOD 25K | Z eval, Z+A funded (own) | -1,336 (41) / -288 (21) / -1 (5) | no |
| Rapid EOD 25K | Z eval, Z+A funded (lanes) | -1,172 (41) / -296 (20) / +0 (5) | no |
| Rapid EOD 25K | Z eval, Z+B funded (own) | -1,592 (43) / -405 (24) / -2 (5) | no |
| Rapid EOD 25K | Z eval, Z+B funded (lanes) | -1,786 (42) / -332 (23) / -2 (5) | no |
| Rapid EOD 25K | Z eval, Z+A+B funded (own) | -1,107 (46) / -301 (23) / +0 (5) | no |
| Rapid EOD 25K | Z eval, Z+A+B funded (lanes) | -1,165 (43) / -125 (24) / +1 (5) | no |
| Rapid EOD 50K (reference) | Z+A (own) | -1,048 (39) / -260 (27) / -17 (10) | no |
| Rapid EOD 50K (reference) | Z+B (own) | -3,144 (87) / -640 (61) / -24 (15) | no |
| Rapid EOD 50K (reference) | Z+B (lanes) | -3,361 (88) / -426 (61) / -21 (15) | no |
| Rapid EOD 50K (reference) | A+B (own) | -1,627 (66) / -1,167 (58) / +13 (17) | no |
| Rapid EOD 50K (reference) | A+B (lanes) | -1,782 (67) / -785 (61) / +18 (17) | no |
| Rapid EOD 50K (reference) | Z+A+B (own) | -77 (52) / +181 (40) / +1 (16) | no |
| Rapid EOD 50K (reference) | Z+A+B (lanes) | +913 (45) / +1,085 (43) / +14 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A funded (own) | -3,008 (76) / -900 (43) / -27 (13) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A funded (lanes) | -2,356 (81) / -704 (41) / -23 (13) | no |
| Rapid EOD 50K (reference) | Z eval, Z+B funded (own) | -3,993 (84) / -1,128 (56) / -31 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+B funded (lanes) | -4,051 (85) / -951 (58) / -30 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A+B funded (own) | -2,558 (84) / -733 (48) / -27 (14) | no |
| Rapid EOD 50K (reference) | Z eval, Z+A+B funded (lanes) | -2,014 (91) / -93 (55) / -24 (14) | no |

## 4. Which account wins and why (best rows, $ a month after fees, Jan-Jun / Jul-Oct / 2021-25)

| Account (price) | Room per $1 of fee | Max micros | Eval rule that matters | Best row that holds up | Its $ a month |
|---|---:|---:|---|---|---|
| **Builder 50K ($91.80)** | $21.8 | 40 | none (1 day, no best-day rule) | Zlarior + ATLAS, own sizes | **$1,888 / $1,286 / $44** |
| Builder 25K ($63) | $15.9 | 20 | none | nothing beats today in every period; best Zlarior + ATLAS + BLITZ | $1,065 / $495 / -$9 |
| Rapid EOD 25K ($97.20) | $10.3 | 20 | best day <= 30% of the profit, 4 days | nothing beats today's preset in every period; best + BLITZ lanes | $2,148 / $1,087 / -$9 |
| Rapid EOD 50K ($165, reference) | $12.1 | 30 | 30%, 4 days | Zlarior + ATLAS + BLITZ lanes (not judged above Zlarior + ATLAS in every period) | $6,370 / $3,298 / $9 |

- The Builder's eval has no best-day rule, so two bots finish it with one or two good days (median 5-7 days). On the
  Rapid EOD every winner is capped by the 30% guard, so more bots help the eval less (25-31 days).
- The Rapid EOD's FUNDED account is the best payer per account (daily payouts, no cap, 90%), which is why the Rapid EOD
  50K reference row is the highest in 2026 - the same finding as rapid-25k-vs-50k-2026-11-17.md (buy the 50K, never the
  25K, if a Rapid is ever bought). The 25K version has half the room: its funded account gets stuck far more often.
- 2 x Builder 25K still makes less than 1 x Builder 50K with the same bots ($889 x 2 = $1,778 vs $1,888 in Jan-Jun,
  $1,068 vs $1,286 in Jul-Oct), and uses 2 of the 5 funded slots.

## 5. Honesty checks

- **Fixed before the results.** The design, the rows and the verdict rule were committed (4e682267) before the first
  full run; nothing was changed after looking. Two diagnostics (per-year, zero-edge placebo) were added after the run;
  they did not change the verdict, they only add caveats.
- **How many were compared:** 7 combos x 4 accounts, multi-bot combos in 2 sizings = 44 main rows; + 44 at +1 tick, 32
  with same-side adds, 24 "Zlarior eval, combo once funded", 16 with the post-close lead = **160 rows x 3 periods = 480
  results**, of which **54 rows** were judged against today's setup. 8 rows passed the rule, all on the Builder 50K; only ONE is
  proposed (Zlarior + ATLAS, own sizes: the owner runs Zlarior + ATLAS only, it does not add eval fails over 60 days in
  2026, and BLITZ is paper). With 54 rows a fluke pass needs > 2 standard errors in three periods at once.
- **Parity:** on the same paths the simulator equals the repo's checked ones with 0 differences: `account4_sim.Ev`,
  `uprisk.Funded` (50K + 25K), `rapid_levers.Rapid` and `rapid_levers.Ev` (Rapid 25K), the cached `engine/account_b`
  sizing (`combo_account.py check`; `tests.test_combo_account`).
- **Placebo (edge set to zero, same timing / stops / swings):** Builder 50K Zlarior + zero-edge ATLAS $388 / $529 /
  -$36 a month, below Zlarior alone ($827 / $714 / -$7); + zero-edge ATLAS and BLITZ $439 / $432 / -$77. The prop firm's
  capped downside does NOT turn extra trades into money by itself: the gain needs ATLAS's real edge.
- **By year (2021-25 split):** Zlarior + ATLAS minus Zlarior alone on the 50K: 2022 **-$113**, 2023 +$84, 2024 +$44,
  2025 +$125 a month (each +-6). In 2021-25 as a whole the combo is ahead on average (+$51) but behind in 65% of runs:
  it buys more evals and lives on the runs where ATLAS gets funded and pays.
- **Monte Carlo noise is not the whole uncertainty.** The standard errors measure the resampling only. Jul-Oct is 78
  trading days, Jan-Jun 128: a different 78 days could move every number. 2026 is an unusually good year for both
  bots; quote the Jul-Oct column.
- **Costs:** +1 tick on every entry and exit lowers most 2026 rows by 2-10% (BLITZ-heavy rows more); the proposal stays ahead in all three periods
  ($1,840 / $1,256 / $26 vs $793 / $696 / -$11).
- **Conflict rule:** the live engine gives Zlarior priority (it closes ATLAS when it enters the other way); here the
  owner's realistic one-account rule is used (first in keeps it). "ATLAS holds, skip Zlarior's opposite entry" was tested
  and rejected on two accounts (b-holds-vs-lit-priority.md, 2021-25 slightly worse). Zlarior priority on one account was
  not tested here. Same-side adds: about the same money on the Builder (+$170 in Jul-Oct, -$140 in Jan-Jun for the
  proposal), more on the Rapid.
- **ATLAS here is the raw member set** (its own one position / 2 a day), not the version cut around Zlarior's other
  account; ATLAS alone on the 25K is therefore a little more active than the live one. The ATLAS members were picked
  with 2021-25 in view, so 2021-25 is not fully out of sample for ATLAS.
- **Model limits:** trades of a day are played in entry order on closed P&L with first-in (no overlap); the adds
  sensitivity adds open losses worst-on-worst; a funded account under its bots' stop-trading room ($100) counts as lost
  (the bot stands down) - earlier studies that never counted it show 0% funded losses. Gaps through stops, platform
  outages and MFFU rule changes are not modelled. BLITZ's size rule exists only for a 25K: x2 on a 50K is an assumption.

## 6. What would make the proposal fail

- A 2022-like year (Zlarior strong alone, ATLAS weak): the shared account gives Zlarior's room to ATLAS and makes ~$113
  a month less than Zlarior alone.
- A 2021-25-like market: both make ~$0; the combo buys ~7 evals in 6 months instead of ~3 (2-week fails 34%).
- ATLAS's live fills worse than 1 extra tick each way, or ATLAS's edge fading (the placebo shows the gain is ATLAS's edge).
- Cross-account clashes: ATLAS also trades its own funded 25K, so a bad ATLAS day hits two accounts; MFFU's no-hedge rule
  across your own accounts still applies (the router must keep blocking opposite positions on the other accounts).
- Building it with a different rule than tested (Zlarior priority, adds, other sizes) - it must be re-run first.

## 7. The Decide card (one, status open)

`tools/web_public/business/decisions.json` id `zlarior-atlas-50k`: "Zlarior's Builder 50K: ATLAS trades it too, from the
eval on (one position at a time, the first one in keeps it)?" - +$572 a month in a Jul-Oct-like market ($2-$1,067 across
runs), +$1,060 Jan-Jun-like, +$51 2021-25-like. A yes replaces the older funded-only card `atlas-on-50k-funded` (its exact
$500-lane version did not hold in 2021-25 here: +$0). Nothing changes until the lead builds it and it is Sim-tested.

Files: `tools/money/combo_account.py` (build-blitz / build / check / study / honesty / table), trades
`research/lab/combo_account_trades.json`, results `research/lab/combo_account.json`, diagnostics
`research/lab/combo_account_honesty.json`, test `python -X utf8 -m tests.test_combo_account` (money area).
