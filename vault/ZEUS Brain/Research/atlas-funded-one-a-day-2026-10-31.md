---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/atlas
type: "research"
date: "2026-10-31"
status: "rejected (no change) - funded max 1 a day loses slot $ in every span (H1 $454 vs $568, H2 $275 vs $382, 2021-25 -$3 vs -$2 a month) and loses even to a random 1-a-day control; the H1 pick (up to 3 a ..."
source: "research/writeups/atlas-funded-one-a-day-2026-10-31.md"
aliases:
  - "ATLAS funded 25K"
---

# ATLAS funded 25K

> [!failure] Verdict: rejected
> rejected (no change) - funded max 1 a day loses slot $ in every span (H1 $454 vs $568, H2 $275 vs $382, 2021-25 -$3 vs -$2 a month) and loses even to a random 1-a-day control; the H1 pick (up to 3 a day) adds +$44 in H1 but exactly $0 in H2 on all 4 path seeds; idea 2 (skip each member's worst VIX band on the funded account) picks nothing - no member lost in any H1 VIX tercile; idea 3 (funded half off at 1R + BE runner) H1 $366 vs $568, H2 $341 vs $382 - rejected, neighbours 0.75R / 1.5R also ...

**Full title:** ATLAS funded 25K - one trade a day (2026-10-31) - fewer trades on the funded account pays the owner LESS; the second trade of the day is part of the money

## Summary

Owner 2026-10-31 "keep building those strategies" - does the FUNDED ATLAS 25K pay the owner more with a day limit of one trade (the day's first ATLAS signal) instead of two? Eval unchanged (today's ATLAS), so only the whole-slot money can move (tools/atx_edge.slot - eval -> funded -> MFFU payouts -> a new $63 eval, 300 paths x 126 sessions). Trade-count rules were tested on the eval path before (atlas-confluences.md), never on the funded account's payouts. Picked on 2026 H1, checked on H2 and 2021-25, random 1-a-day control (4 seeds), neighbours max 3 / max 4, 4 path seeds.

## Money first

**No change for ATLAS. Keep 2 trades a day on the funded 25K.**

"Slot $" = what one ATLAS 25K slot pays YOU a month over 6 months: the eval, the funded account, MFFU's payouts (80% to
you), and a new $63 eval after every fail, stuck account or graduation (same simulator as `atlas-edge-2026-10-30b.md`).
The eval does not change in any row (same trades, same 2-week pass / dead), so slot $ is the only number that can move.

| ATLAS funded 25K | H1 slot $/mo | **H2 slot $/mo** | 2021-25 slot $/mo | % of slot paths that lose H1 / H2 / 2021-25 | Verdict |
|---|---:|---:|---:|---|---|
| **Today (max 2 a day)** | $568 | **$382** | -$2 | 6.7 / 18.0 / 72.6 | |
| Max 1 a day (the day's first signal) | $454 | **$275** | -$3 | 8.3 / 21.0 / 73.9 | worse everywhere |
| Max 3 a day (the H1 pick) | $612 | **$382** | +$4 | 5.3 / 18.0 / 71.1 | H2 +$0: fails |
| Max 4 a day (neighbour) | $612 | $382 | +$4 | same as max 3 | = max 3 (never a 4th) |
| Control: 1 random signal a day (4 seeds, mean) | $541 | $361 | +$7 | | beats "first signal only" |

- **One a day costs the owner about $110 a month** in both 2026 halves (-$114 H1, -$107 H2). Same on every path seed
  (seeds 5 / 11 / 41: H1 $470-477 vs $573-595, H2 $252-272 vs $347-374).
- **Taking only the FIRST signal is worse than taking a random one.** 1 random signal a day averages $541 / $361 a
  month; the first signal only $454 / $275. The day's later ATLAS signals carry real money; cutting them throws it away.
- **The H1 pick (up to 3 a day) is H1-only money.** +$44 a month in H1, but a 3rd funded trade never happens in H2: the
  H2 slot is identical to today on all 4 seeds ($382 / $367 / $347 / $374). In 2021-25 +$6 a month
  (noise; the account loses there either way). It fails the gate (the slot must be up in H2 too).
- **Why it was worth a look.** On the funded account the payout rules reward steady days (the 50% best-day rule, the
  trailing floor), so fewer, cleaner trades could have paid more. They don't: on the real 2026 path the funded trades of
  "max 1" have a similar PF in H1 (3.17 vs 2.94) but a lower one in H2 (2.45 vs 2.96), and fewer payouts.

**Idea 2, same session: skip each member's worst VIX band on the funded account only (eval unchanged).** Nothing to
skip. VIX bands = terciles of the prior day's CBOE VIX close over 2026 H1 sessions (under 17.37 / 17.37-19.50 / over
19.50, frozen). In H1 every member made money in every band (R per trade: EMA +0.55 / +0.83 / +0.75, MACD +1.10 / +1.95
/ +1.09, S/R +0.91 / +0.80 / +1.14; 7-22 trades each), so the pre-declared rule (drop a band only if it lost in H1) picks
nothing and the funded slot stays today's ($568 / $382 / -$2). Dropping a winning band would cost money in H1 by
construction. VIX per member was already rejected on the eval (atlas.md); this closes it for the funded account too.
Numbers: `research/second/atx_funded_vix.json` (no run stored: identical to `atxd_today`).

**Idea 3, same session: a partial on the funded account (half off at 1R, the stop to breakeven, the rest on today's
exit; eval unchanged). Rejected: it costs the owner about $200 a month in H1.**

| Funded 25K exit | H1 slot $/mo | H2 slot $/mo | 2021-25 slot $/mo | Funded trades (real path) H1 / H2: PF, R per $ risked |
|---|---:|---:|---:|---|
| **Today (no partial)** | **$568** | **$382** | -$2 | 2.94, +0.867 / 2.96, +0.657 |
| Half off at 0.75R + BE (neighbour) | $336 | $203 | -$21 | |
| **Half off at 1R + BE** | $366 | $341 | -$14 | 1.94, +0.404 / 3.27, +0.558 |
| Half off at 1.5R + BE (neighbour, best of the three in H1) | $414 | $388 | -$6 | 2.07, +0.471 / 4.06, +0.739 |
| Control: the 1R partial on a random half of the trades (4 seeds) | $389-448 | $273-327 | -$15 to +$3 | |

- Every partial loses H1 money, and more partials = less money (0.75R worst, the random half in between). The
  partial cuts ATLAS's big winners: at 1R, 684 of 1,395 member trades change, -0.23R each on average (H1: 72 trades, -62R).
- The H1 pick among partials (1.5R) is still $154 a month below today in H1. In H2 it is +$6 (+$25-33 on the other
  seeds) with a smaller funded drawdown (-$386 vs -$1,175), but it is worse in 2021-25 on every seed (-$6 to -$20 vs
  -$2 to -$11). It fails the gate; at most a note that a 1.5R partial smooths the H2 funded path.
- Path: the members' own bars (1m in 2026, 5m before), highs and lows after the entry bar; a bar touching both the stop
  and the partial level counts as the stop first; a bar after the partial touching the entry = the runner out at
  breakeven less 1 tick. With 1 micro the split is a blend (half the points), as the simulator sizes in whole micros.
- Runs `atxd_partial_p1`, `atxd_partial_p1p5`; numbers `research/second/atx_funded_partial.json`.

**Idea 4, same session: a re-entry after a stop-out on the funded account (eval unchanged). Rejected: about -$160 a
month in H1 and -$125 in H2.** The member records hold one trade per member per day, so there is no "next signal" of
the same member; the test re-takes the same setup once: after a stop before 15:00 ET, enter at the next bar's open in the
same direction, the same risk, the first trade's target price, flat 15:55 (a bar touching both = stop first; 1 tick
slippage on the entry and on a stop). The re-entry counts toward the 2 a day.

| Funded 25K | H1 slot $/mo | H2 slot $/mo | 2021-25 slot $/mo | Re-entries (all candidates) H1 / H2 / 2021-25: n, sum R |
|---|---:|---:|---:|---|
| **Today (no re-entry)** | **$568** | **$382** | -$2 | |
| **Re-entry, same risk** | $404 | $257 | -$15 | 49, -11.8R / 19, -5.0R / 601, -16.2R |
| Re-entry, 1.5x the risk (neighbour, fewer micros) | $492 | $213 | -$2 | 49, -3.8R / 19, -7.1R / 600, -8.3R |
| Control: the re-entry in a coin-flip direction (4 seeds) | $401-590 | $154-259 | -$10 to -$9 | |

- Lower on every path seed (H1 $404-439 vs $568-595, H2 $254-270 vs $347-382). The re-entries lose R in every span, and
  the same-direction rule sits inside the coin-flip control's range: after an ATLAS sto

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-31]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas|ATLAS]], [[atlas-edge-2026-10-30b|ATLAS edge, day session]]
- Runs: `atxd_max1, atxd_max3, atxd_today, atxd_partial_p1, atxd_partial_p1p5, atxd_reentry_1r`
- Source: `research/writeups/atlas-funded-one-a-day-2026-10-31.md`
- Back to [[ZEUS Home]]
