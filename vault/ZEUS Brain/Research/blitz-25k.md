---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/blitz
type: "research"
date: "2026-10-29"
status: "no adopt-candidate - no BLITZ rule change holds in 2026 H1, H2 and 2021-25 (0 of 1,997 variants); verdict no-change (research/scalp/blitz_25k_pick.json). Only the 25K eval size for its own account ..."
source: "research/writeups/blitz-25k.md"
aliases:
  - "BLITZ on its own MFFU Builder 25K"
---

# BLITZ on its own MFFU Builder 25K

> [!success] Verdict: adopt-candidate
> no adopt-candidate - no BLITZ rule change holds in 2026 H1, H2 and 2021-25 (0 of 1,997 variants); verdict no-change (research/scalp/blitz_25k_pick.json). Only the 25K eval size for its own account changes (40% of the room, then 100% from session 5): about 72% of evals decided in 2 weeks instead of 40%, same money. The 25K slot still loses about $40 a month in 2021-25 with every setting. Paper only, nothing switched.

**Full title:** BLITZ on its own MFFU Builder 25K (account C) - keep today's rule; trading "like a person" (structure stops, liquidity targets, swing trails, change-of-character exits) does not beat it in both 2026 halves and 2021-25; the anti-hedge rule costs nothing; size the eval for speed (same money)

## Summary

Owner 2026-10-28/29 - BLITZ gets its own MFFU Builder 25K next week; make it trade "like a person, not a fixed rr" and "learn market structure", judged on money and eval speed. Every variant ran as account C (never opposite LIT or ATLAS, closed first at their opposite entry), 2026 on 1m bars (pick on Jan-Jun, check on Jul-Oct 16), 2021-25 the same rule on 5m bars, costs in ($1.90 a micro, 1 tick on market / stop fills, same-bar tie = loss). The anti-hedge rule costs nothing in 2026 (+$51 / +$90 a month at $150 a trade; of 330 trades 12 skipped, 5 added, 1 closed early) and $16 a month in 2021-25. Structure stops (45: last 1m / 5m swing, the move's low, min / max caps) make less than today in H1 and 2021-25 (most lose in 2021-25). Targets at the next liquidity, partials at the first level, swing trails, change-of-character exits and no clock (1,920 variants on 5 stops): 18 beat today in H1 on avg R and $ a month, 4 also in H2 and 2021-25, none also on the 25K eval. Opening drive, London continuation, retest limit entries and 15m / 1h structure filters (32): none. Today's rule on the 25K, best size picked on H1 (40% of the room, 100% from session 5; funded 1 micro, +$400 day stop): 2-week pass / fail 36.1 / 37.8, 36.2 / 34.8, 20.4 / 50.2 (H1 / H2 / 2021-25), decided in 2 weeks 74 / 71 / 71%, slot $270 / $37 / -$40 a month; today's paper size $251 / $40 / -$34 with only 29-41% decided. Random-direction trades make the same H2 slot money ($30): outside H1 the 25K is an eval lottery.

## Money first

**Short answer: keep BLITZ's rule exactly as it is. Nothing "like a person" beat it in all three test periods.** On its own
25K the only useful change is the eval size: it decides the eval faster, but it does not make more money. In 2021-25-like
markets the account still loses about $40 a month. BLITZ on its own 25K is a bet that the 2026 market continues.

**BLITZ as it will trade on account C** (today's rule, never opposite LIT or ATLAS; fixed $150 risk a trade = 1 micro at a
~60-point stop; 2026 on 1m bars, 2021-25 the same rule on 5m bars):

| Span | Trades | / week | Weeks with 2+ | Win % | Avg R | PF | Net | **$ / month** | Max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026 H1 (pick) | 217 | 8.5 | 89% | 56.7 | +0.165 | 1.70 | +$5,873 | **+$963** | -$1,152 |
| **2026 H2 (check)** | 106 | 6.8 | 75% | 56.6 | +0.200 | **1.62** | **+$2,478** | **+$667** | -$815 |
| 2021-25 (5m) | 1,841 | 8.6 | 80% | 50.1 | +0.013 | 1.05 | +$3,765 | +$73 | -$5,512 |
| same rule alone (no anti-hedge rule) H1 / H2 / 2021-25 | 221 / 109 / 1,869 | | | | +0.150 / +0.171 / +0.016 | 1.63 / 1.49 / 1.06 | | +$912 / +$577 / +$89 | |

**The 25K eval and the whole account slot** (MFFU Builder 25K: $63, +$1,500 target, $1,000 end-of-day trailing loss
locked at start + $100, $600 soft daily loss; a fresh eval on every session; "slot" = buy the eval, pass, 2 sessions of
paperwork, the funded 25K, payouts at 80%, a new eval after a fail / stuck / lost account; 6-month Monte Carlo paths in
5-session blocks, net of every eval bought). Funded size for every row: 10% of the room, at most $150 (1 micro), no new
trade after +$400 on the day.

| Eval size (today's rule, account C) | 2-week pass / fail H1 | H2 | 2021-25 | decided in 2 wks H1 / H2 / 2021-25 | passes slower than 3 wks | median sessions to pass | **slot $ / month H1 / H2 / 2021-25** |
|---|---:|---:|---:|---:|---:|---:|---:|
| 40% of the room, <= $600 (the paper ledger today) | 32.8 / 8.4 | 36.2 / 2.9 | 15.8 / 13.1 | 41 / 39 / 29% | 23 / 5 / 11% | 9 / 6.5 / 6 | $251 / $40 / -$34 |
| 60% of the room, <= $600 (scalp-na-mffu's slot) | 31.1 / 40.3 | 29.0 / 33.3 | 18.4 / 38.0 | 71 / 62 / 56% | 11 / 4 / 6% | 6 / 5 / 4 | $258 / $39 / -$42 |
| 100% of the room, <= $600 | 37.8 / 40.3 | 30.4 / 42.0 | 20.8 / 54.3 | 78 / 72 / 75% | 10 / 0 / 4% | 5 / 5 / 4 | $273 / $36 / -$42 |
| **40%, then 100% from session 5 (pick)** | **36.1 / 37.8** | **36.2 / 34.8** | 20.4 / 50.2 | **74 / 71 / 71%** | **10 / 0 / 6%** | 6 / 5 / 6 | **$270 / $37 / -$40** |
| 40%, then 100% from session 8 | 35.3 / 21.8 | 39.1 / 20.3 | 19.2 / 38.9 | 57 / 59 / 58% | 13 / 2 / 7% | 8 / 6 / 7 | $266 / $38 / -$39 |
| 50%, no new trade after -$250 on the day | 31.9 / 26.9 | 34.8 / 1.4 | 16.6 / 22.1 | 59 / 36 / 39% | 12 / 13 / 8% | 7 / 8.5 / 5 | $247 / $42 / -$39 |
| "need": what is left to pass / 2, <= 80% of the room | 25.2 / 37.8 | 17.4 / 31.9 | 10.6 / 44.2 | 63 / 49 / 55% | 26 / 4 / 20% | 10 / 9 / 9.5 | $255 / $36 / -$37 |

In plain words:
- **The money barely moves with the size** ($247-273 a month in H1, $36-42 in H2, -$34 to -$42 in 2021-25). The size only
  decides **how fast** the eval ends. The owner's rule is "passed or failed within 2 weeks, never more than 3 weeks to
  pass": the pick (40% for the first 4 sessions, then the full room from session 5) decides 71-74% of evals in 2 weeks and
  fewer than 10% of passes take longer than 3 weeks. Today's paper size leaves about 60% of evals undecided after 2 weeks.
- The price of speed: about as many evals fail as pass in 2026 (36 / 35-38), and in 2021-25 two fail for every pass. Each
  fail costs $63.
- **Once funded, the 25K gets stuck.** With a 60-point stop one micro risks about $122, so the $1,000 trailing room is only
  about 8 losses. In H1 45% of funded accounts got stuck under the floor before paying much ($108 a month funded); in H2
  every funded start got stuck ($0, only 6 starts); 2021-25 $2 a month. That is why the slot pays little.
- **Random directions** on the same signal bars (8 seeds, the pick's sizes) make -$49 / **+$30** / -$67 a month against the
  real $270 / **$37** / -$40. In H1 the edge shows; **in H2 the 25K slot money is no better than coin flips**: it is the
  eval lottery ($63 tickets with a ~1-in-3 pass), not BLITZ's edge.
- Compared with scalp-na-mffu.md's own-25K numbers ($224 / $3 / -$40 a month, BLITZ alone): **+$46 / +$34 / $0**, from the
  anti-hedge rule (+$31 / +$30 / -$1) and the faster size.

**What the anti-hedge rule costs (account C vs BLITZ alone):**

| | Trades skipped / added / closed early | $ / month at $150 a trade | 25K slot $ / month (pick's sizes) |
|---|---:|---:|---:|
| 2026 H1 | 9 / 5 / 0 (of 221) | $912 -> $963 | $239 -> $270 |
| 2026 H2 | 3 / 0 / 1 (of 109) | $577 -> $667 | $7 -> $37 |
| 2021-25 | 44 / 16 / 16 (of 1,869) | $89 -> $73 | -$39 -> -$40 |

"Added" = a later check that could trade because the skipped one no longer held the slot. **It costs nothing in 2026** (the
12 skipped 2026 trades averaged -0.14R: against LIT's or ATLAS's open side BLITZ mostly lost) and about $16 a month at $150
a trade in 2021-25 (there the 44 skipped trades averaged +0.11R). The stricter version, also never opposite a LIT setup
that is armed (limit working / waiting for its 1m CISD), is as good: $1,006 / $661 / $100 a month at $150. The engine can
use the strict version.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-29]]
- Strategies: [[BLITZ (paper)]]
- Refers to: [[scalp-na-mffu|BLITZ]]
- Runs: `blitz25k_today_acct_c, blitz25k_h1pick, blitz25k_structure`
- Source: `research/writeups/blitz-25k.md`
- Back to [[ZEUS Home]]
