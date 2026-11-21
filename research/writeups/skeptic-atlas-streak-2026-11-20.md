---
title: Skeptic check of Decide card atlas-funded-streak-1micro (after 2 ATLAS losses in a row, 1 micro until a win) - WEAKER THAN CLAIMED; spot check of rapid25-lit-bank (NO holds) and atlas-on-rapid (YES holds)
family: second
date: 2026-11-20
status: verdicts - atlas-funded-streak-1micro WEAKER THAN CLAIMED (card text updated, recommend kept yes with a caveat); rapid25-lit-bank NO HOLDS; atlas-on-rapid YES HOLDS. Nothing live changed.
summary: Lead round 3 (day-newstrat). Re-ran the card's own simulator (tools/atlas_edge.py PGE -> atlas_risk PGF3, today's $887-room funded 25K, 10 and 6 ticks a side, 1,000 paths) and reproduced it exactly (10t lost 17.6 -> 12.2% Jan-Jun-like, 21.7 -> 10.9% Jul-Oct-like, $503 -> $481 / $402 -> $408). Code: no look-ahead (the streak only reads finished sessions), both arms on the same trades / costs / paths, room and floor math untouched. Holds on 2 more seeds (Jul-Oct-like 23.5 -> 12.5%, 23.8 -> 11.7%) and lowers the loss odds in every 2021-25 year (but 89-99% are still lost). Weaker: (1) shuffling single days instead of week blocks halves the gain (Jul-Oct-like 23.5 -> 18.5%) and costs $53 a month (-14%, under the card's own 90% money bar); the effect leans on losses arriving in bunches. (2) In a Jan-Jun-like market a plain flat smaller size beats it on both counts (room 40%: 11.0% lost, $527 vs the rule's 12.2%, $481), so there it is just "trade smaller". (3) It is not a knife edge: 3 losses -> 1 micro (13.9% / $418) and 2 losses -> 2 micros (11.8% / $422) work in Jul-Oct-like too, and cost less in Jan-Jun-like; 1 loss over-shrinks ($304); a per-leg streak is worse (18.1%). (4) On top of room 40% it cuts Jul-Oct-like loss odds 14.0 -> 7.7% at the same $ but costs $49 a month Jan-Jun-like for only 11.0 -> 10.1%. Rapid spot check: both card verdicts follow their pre-registered rules and the stored numbers.
runs: none (research/skeptic/streak.py -> research/skeptic/streak_results.json)
---

## For the owner

| Card | Verdict | In $ |
|---|---|---|
| ATLAS funded: after 2 losses, 1 micro until a win | **Weaker than claimed** (still safer, costs more) | Safer in every test. Cost -$22 to -$49 a month in a Jan-Jun-like market, $0 to -$53 Jul-Oct-like depending on the test |
| Rapid 25K: Zlarior 1 micro + bank at the room | **NO holds** | +$24 / +$101 a month, but the eval fails 6x as often in a Jan-Jun-like market (0.5% -> 3.1%) |
| Rapid: ATLAS next to Zlarior | **YES holds** | +$1,662 / +$609 a month; without ATLAS half the runs never get paid |

Plain version of the streak card: it is real protection, but most of it is "trade smaller". Its extra value comes when
losing trades come in bunches (a Jul-Oct-like market). If you tap **room 40%** first, the streak rule on top roughly halves
the chance of losing the account in a Jul-Oct-like market (14% -> 8%) for the same money, and costs about $49 a month in a
Jan-Jun-like one. Say yes if keeping the account matters more than that.

## 1. Code read (tools/atlas_edge.py, PGE)

| Check | Finding |
|---|---|
| Look-ahead | None. `qty()` reads `self.streak`, which `step()` updates only from the session's finished trades (kp) after the session |
| Same trades / fills / costs in both arms | Yes: one `T = to_T(opt_units("base", n))`, one `BY`, the same `PF` paths; only `qty` differs |
| Room / trailing floor | Untouched: the guard only lowers `q` after `PGF3.qty` (room %, stuck, caps), and only when q > 1 |
| Trade order across legs | One position + max 2 a day (atlas_revive.one_pos), in entry order: same as the base |
| Things the live build must copy (not bugs) | (a) the streak updates at the END of a session, so a same-day 2nd trade does not see the 1st trade's loss; (b) a loss = net $ < 0, so a 1-micro breakeven scratch (-$3.80) counts as a loss and extends the 1-micro spell; (c) in the Monte Carlo the streak carries across stitched week blocks (same for both arms) |

## 2. Re-runs (10 ticks a side, today's account; $ a month to you / lost in 6 months)

| Paths | No rule H1 | Rule H1 | No rule H2 | Rule H2 | No rule 2021-25 | Rule 2021-25 |
|---|---|---|---|---|---|---|
| week blocks seed 23 (the card) | $503 / 17.6% | $481 / 12.2% | $402 / 21.7% | $408 / 10.9% | $19 / 98.8% | $18 / 96.3% |
| week blocks seed 101 | $505 / 18.2% | $476 / 13.3% | $395 / 23.5% | $404 / 12.5% | $18 / 98.9% | $19 / 95.8% |
| week blocks seed 7,942 | $497 / 18.6% | $471 / 14.5% | $389 / 23.8% | $400 / 11.7% | $20 / 99.3% | $20 / 96.6% |
| **day blocks** seed 23 | $473 / 20.5% | $450 / 16.6% | $372 / 23.5% | **$319 / 18.5%** | $14 / 99.4% | $15 / 97.3% |

2021-25 year by year (week blocks): 2021-22 99.3 -> 93.6%, 2023 99.5 -> 98.1%, 2024 99.6 -> 98.6%, 2025 97.2 -> 89.0% lost; $ a month
$14-38 either way. At 6 ticks every row moves the same way (e.g. card paths 12.9 -> 9.2% / 16.8 -> 7.8%; day blocks H2 $409 -> $351).

## 3. Neighbours and "just trade smaller" (10 ticks, card paths; avg micros a trade in brackets)

| Version | H1 $ / lost | H2 $ / lost | 2021-25 lost |
|---|---|---|---|
| no rule (60% of room) | $503 / 17.6% (2.10) | $402 / 21.7% (2.22) | 98.8% |
| **2 losses -> 1 micro (card)** | $481 / 12.2% (1.77) | $408 / 10.9% (1.79) | 96.3% |
| 1 loss -> 1 micro | $457 / 10.8% (1.54) | $304 / 10.9% (1.45) | 92.9% |
| 3 losses -> 1 micro | $491 / 14.8% (1.90) | $418 / 13.9% (1.98) | 97.6% |
| 2 losses -> 2 micros | $499 / 15.0% (1.93) | $422 / 11.8% (1.91) | 97.1% |
| 2 losses -> 3 micros | $502 / 16.7% (2.01) | $426 / 12.2% (1.99) | 98.6% |
| 2 losses of the same leg (per-leg reset) | $523 / 10.3% (1.68) | $318 / 18.1% (1.74) | 96.4% |
| flat 50% of room | $517 / 14.1% (2.06) | $401 / 17.6% (2.15) | 98.7% |
| flat 40% of room | $527 / 11.0% (2.01) | $393 / 14.0% (2.03) | 98.2% |
| flat 30% of room | $522 / 9.9% (1.93) | $351 / 14.4% (1.82) | 98.1% |
| room 40% + the card's rule | $478 / 10.1% (1.71) | $394 / 7.7% (1.68) | 94.9% |
| room 40% + rule, seed 101 | $473 / 11.1% vs room 40% alone $515 / 13.8% | $390 / 9.0% vs $392 / 16.4% | |
| room 40% + rule, day blocks | $452 / 13.5% vs $478 / 17.1% | $313 / 11.8% vs $358 / 16.5% | |

Reading: in a Jan-Jun-like market a flat 30-40% beats the rule on money AND safety with as many or more contracts, so there
the rule is only "smaller". In a Jul-Oct-like market the rule beats a flat size of the same average contracts (10.9% vs 14.4%
lost, $408 vs $351): the timing adds something there, and it is larger when losing days stay together (week blocks) than
when they are shuffled (day blocks). Not a knife edge: 2 -> 2 micros and 3 -> 1 micro sit close by.

## 4. Rapid spot check (tools/money/rapid25_launch.py on day-rapid, its stored research/lab/rapid25_launch.json)
- **atlas-on-rapid YES holds.** Its pre-registered rule (10 ticks: both > LIT alone in $ and fewer no-payout runs in H1 and H2):
  $1,883 vs $221, $800 vs $191; no payout 7.4% vs 55.0%, 15.1% vs 50.0%. The card's +$1,662 / +$609 / -$28 match. Worth knowing
  (not in the card): in a 2021-25-like market the eval fails 77% of the time with ATLAS vs 3.5% for LIT alone (both ~$0 a month).
- **rapid25-lit-bank NO holds**, by the 1-point eval-fail limit fixed before the run (H1 0.5 -> 3.1%, 2,000 eval paths: well
  outside noise). It is a close call, not a harm: +$24 / +$101 a month, Jul-Oct-like eval pass 85.5 -> 92.0%; the card says so.
- Code: same paths for every row, ATLAS re-priced at 10 ticks for every row that has ATLAS, LIT row reused (no ATLAS to
  re-price): fine. The judge reads the 10-tick rows only, as designed.

## Card change made
`tools/web_public/business/decisions.json` atlas-funded-streak-1micro: `risk` gets the day-shuffle and room-40% numbers, and
`recommend_why` now says it is mostly "trade smaller" in a Jan-Jun-like market and worth it mainly with room 40% in a
Jul-Oct-like one. `recommend` kept "yes" (it still makes losing the account less likely in every test); status stays open;
$ fields unchanged (they are the card's own reproduced numbers). The two Rapid cards were not touched (verdicts unchanged;
they live on day-rapid).
