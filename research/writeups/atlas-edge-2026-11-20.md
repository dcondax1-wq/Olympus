---
title: ATLAS edge at real fills - 1 of 15 changes passes (after 2 losses in a row, 1 micro until a win); limit orders, later entries, dropping / halving EMA and ES legs all fail
family: second
date: 2026-11-20
status: one Decide card (atlas-funded-streak-1micro, recommend yes, open). Nothing live changed. 14 rejected (TESTED_AND_REJECTED). ES legs: no. Fresh data to Nov 19: edge holding (edge check AMBER -> GREEN).
summary: Pre-registered (research/second/atlas_edge_design.md, commit 5b511c92, before any run), judged at 6 and 10 ticks a side on today's funded 25K ($887 room) with both today's 60% sizing and the room-40% card. Passes - E3, after 2 losing ATLAS trades in a row trade 1 micro until the next winner. At 10 ticks from today's account the chance of losing the funded 25K in 6 months goes 17.6 -> 12.2% (Jan-Jun-like) and 21.7 -> 10.9% (Jul-Oct-like) for $503 -> $481 / $402 -> $408 a month; first payout about a week later (Dec 30 / Jan 12). With room 40% as well: 10.1 / 7.7% lost, $478 / $394. Holds on a second set of random paths; neighbours (1 and 3 losses) behave monotonically. Fails - limit orders at or better than the 5m open with 1-2 minute timeouts (only ~52% of signals fill; missed winners cost $28-37k at $250 a trade over 2021-26), limit then market, the next 5m open, per-leg minutes (MACD +1 minute looks good on Jul-Oct but needs 1m bars, info only), dropping or halving EMA (the leg that loses most to slippage, but also the 2026 earner), day stop after a loss, 3-loss pause, a weekly cap. ES versions of all 3 legs lose in 2026 (PF 0.6-0.9 vs NQ 1.2-3.3).
runs: tools/atlas_edge.py run / posthoc / es -> research/second/atlas_edge.json; tools/atlas_es.py run -> research/second/atlas_es_trades.json
---

# ATLAS edge at real fills (2026-11-20)

## For the owner (one minute)

**One change works: when ATLAS loses 2 trades in a row, it trades 1 micro until it wins again. Same money, the funded 25K is
lost about half as often before payday. Everything else tested (limit orders, later entries, dropping a strategy, ES) made
less money. Tap YES on the new Decide card; also keep your YES on "room 40%".**

At real fills (10 ticks a side), from today's account ($24,887, $887 room), next 6 months:

| Setup | Jan-Jun-like: $ a month, 1st / 2nd payout, lost | Jul-Oct-like | 2021-25-like (calm) |
|---|---|---|---|
| Today (60% of the room) | $503, Dec 23 / Jan 27, lost 17.6% | $402, Jan 7 / Feb 22, lost 21.7% | $19, none, 98.8% |
| Room 40% (card already yes) | $527, Dec 29 / Jan 29, lost 11.0% | $393, Jan 19 / Mar 4, lost 14.0% | $16, none, 98.2% |
| **2 losses -> 1 micro (new card)** | **$481, Dec 30 / Feb 8, lost 12.2%** | **$408, Jan 12 / Feb 26, lost 10.9%** | $18, none, 96.3% |
| **Both** | **$478, Jan 6 / Feb 11, lost 10.1%** | **$394, Jan 20 / Mar 8, lost 7.7%** | $18, none, 94.9% |

"Lost" = the account closed (floor, or the room too small for a micro and MFFU's 7-day inactivity close). Chance of losing it
**before the first payout**: today 13.9 / 16.7%, room 40% 9.3 / 11.7%, the new rule 10.4 / 9.4%, both 8.5 / 6.4%.
In a calm 2021-25-like market ATLAS loses the account almost surely whatever we do; no rule fixes that.

**Next for you:** tap YES on "after 2 losing trades in a row, trade 1 micro until the next win". Claude builds it (Sim check
first). Nothing else.

## What was asked and the answer

| Job | Result |
|---|---|
| (a) limit order at / better than the signal price, timeout | **No.** Only about half the signals fill (665 of 1,288 signals, 2021-26); the ones that don't are the runners. Funded $ falls to $246-285 a month (Jan-Jun-like) and the loss chance doubles |
| (b) leg that loses most to slippage | **EMA** (London EMA pullback): -$257 a month at $250 a trade from 1 to 10 ticks (MACD -$114, S/R -$52). But it is also the leg that earns 2026: dropping it leaves $101 a month Jul-Oct-like (loss chance 48.8%); half size $303. Keep it |
| (c) entry minute per leg | **No change.** The next 5m open loses $133 a month Jul-Oct-like. Per-leg minutes picked on Jan-Jun: EMA +0, MACD +1, S/R +0; Jul-Oct $436 vs $402, but 2021-25 has no 1m bars, so it can't be proven (info only) |
| (d) ES version of each leg | **No.** All 3 legs lose on ES in 2026 at real-fill-equivalent costs (PF 0.66-0.84 Jan-Jun, 0.60-1.44 Jul-Oct) where NQ makes PF 1.2-3.3 |
| (e) funded guards | **One passes:** 2 losses in a row -> 1 micro until a win. The day stop after a loss, a 3-session pause after 3 losses and a weekly cap at 35% of the room all lose more accounts or more money |
| (f) payout path | Table above. The new rule moves the first payout about 1 week later and cuts the chance of losing the account before it by about a third (Jan-Jun-like) to almost half (Jul-Oct-like) |

## Method (pre-registered, research/second/atlas_edge_design.md, commit 5b511c92 before any run)

- Trades: the live ATLAS units (tools/atlas_more.base_units: never opposite LIT incl. its armed setups), one position, max 2
  a day. Costs: N ticks a side (tools/atlas_fills.priced: entry N past the 5m open, non-target exits N past the level,
  targets 0). Judged at 6 AND 10 ticks (10 = the stress; the 3 real fills ran ~11); 1 and 3 shown.
- Funded 25K: tools/atlas_risk PGF3 (MFFU Builder 25K funded rules, the live funded preset, min_room 0, the inactivity
  close) from today's account, 1,000 week-block paths per market (H1 = 2026 Jan-Jun, H2 = Jul-Oct, REF = 2021-25), the same
  paths for every option. The base reproduces this morning's atlas-risk numbers exactly ($503 / 17.6%, $527 / 11.0%).
- Fixed view: $250 a trade, real days (H1, H2, 2025, 2021-24), costs in.
- Gate G (entry / leg changes): funded $ +$10 in H1 and H2, REF not -$5, loss chance not +0.5 anywhere, PF not lower, fixed
  $ not -$10 in any span, 2-4.1 trades a week, testable on 2021-25, at 6 and 10 ticks, on 60% AND 40% sizing.
  Gate E (guards): loss chance down 0.5+ point in H1 and H2 (REF not up 0.5), $ at least 90% of the base in H1 and H2
  (REF within $10), at 6 and 10 ticks, on 60% AND 40%.

## Results at 10 ticks (60% sizing; 6 ticks and 40% in research/second/atlas_edge.json)

Base: fixed view H1 4.06 trades a week, PF 2.39, $2,614 a month, max DD -$1,476; H2 2.95, PF 2.07, $1,172, -$1,177; 2025
4.30, PF 0.90, -$269; 2021-24 4.71, PF 0.80, -$638. Funded $503 / $402 / $19 a month, lost 17.6 / 21.7 / 98.8%.

| Option | Signals filled / skipped | Funded $ a month H1 / H2 / REF, lost H1 / H2 | Fixed PF H1 / H2 / 2021-24 | Verdict |
|---|---|---|---|---|
| A1 limit at the open, 2 min | 665 of 1,288 fill; missed $31.5k | $282 / $320 / $2, 36.4 / 12.7% | 2.09 / 2.46 / 0.52 | no |
| A2 limit 1 tick better, 2 min | 659 fill; missed $30.3k | $285 / $320 / $3, 35.7 / 13.6% | 2.12 / 2.49 / 0.53 | no |
| A3 limit 2 ticks better, 2 min | 642 fill; missed $28.8k | $246 / $348 / $3, 38.8 / 9.4% | 2.04 / 2.67 / 0.55 | no |
| A4 limit 2 min, then market | 665 fill + 613 chased | $407 / $240 / $8, 23.7 / 39.5% | 2.10 / 1.81 / 0.64 | no |
| A5 limit at the open, 1 min | 638 fill; missed $36.7k | $151 / $74 / $2, 48.7 / 18.5% | 1.88 / 1.46 / 0.52 | no |
| B1 drop EMA | 579 EMA signals gone | $501 / $101 / $19, 8.9 / 48.8% | 2.89 / 1.31 / 0.87 | no |
| B2 EMA at half size | | $540 / $303 / $20, 9.9 / 24.9% | 2.57 / 1.70 / 0.83 | no |
| B3 EMA +60 s (info, 1m only) | | $512 / $345, 16.3 / 29.6% | 2.25 / 1.78 | info |
| C1 per-leg minute (info, 1m only) | EMA 0, MACD +1, S/R 0 | $508 / $436, 16.5 / 18.9% | 2.61 / 2.07 | info |
| C2 next 5m open (+5 min) | 72 skipped | $496 / $269 / $18, 14.0 / 23.0% | 2.08 / 1.50 / 0.74 | no |
| C3 per leg +0 or +5 (picked on H1) | all legs picked +0 | = today | = today | no change |
| E1 day stop after a loss (re-check) | | $425 / $252 / $16, 20.6 / 33.9% | (sizing only) | no |
| E2 3 losses -> 3 sessions off | | $419 / $357 / $19, 20.9 / 21.0% | | no |
| **E3 2 losses -> 1 micro until a win** | | **$481 / $408 / $18, 12.2 / 10.9%** | | **pass** |
| E4 week cap 35% of the room | | $492 / $358 / $18, 18.5 / 31.6% | | no |

Why the limits fail: ATLAS's late fills are price running its way in the first seconds after the 5m close. A limit at the
open only fills when price comes back, and about half the time it never does; those are the trades that run to the VIX-band
target. Fill probability ~50% in every variant, and the missed winners are worth far more than the 10 ticks saved.

Per leg, $250 a trade (PF, $ a month), 1 -> 10 ticks:

| Leg | 2026 Jan-Jun | Jul-Oct | 2025 | 2021-24 |
|---|---|---|---|---|
| EMA | 2.66 $1,322 -> 2.05 $1,065 | 4.93 $1,064 -> 3.33 $914 | 0.87 -$144 -> 0.62 -$566 | 1.07 $81 -> 0.73 -$415 |
| MACD | 3.19 $1,145 -> 2.70 $1,031 | 1.44 $168 -> 1.21 $92 | 1.35 $268 -> 1.12 $107 | 1.07 $67 -> 0.86 -$166 |
| S/R | 3.59 $783 -> 3.23 $731 | 1.84 $294 -> 1.62 $240 | 1.33 $208 -> 1.12 $85 | 1.05 $39 -> 0.87 -$114 |

EMA pays the most for slippage (most trades, the tightest stops), and it is still the best leg in 2026; in 2021-25 every leg
loses at 10 ticks.

### ES (job d; tools/atlas_es.py, helper)

The research generators run on ES 5m bars (2025-04-14 onward only, so 2021-24 can't be tested), NQ-point params x 0.28.
Method check on NQ: entries 100% equal for all 3 legs over the whole history, exits 100% for EMA and S/R, MACD 362 of 387
(ES has no 1m bars). ES costs: the NQ delay in price terms (10 NQ ticks = 3 ES ticks) and a 10 ES-tick stress. MES $5 a point.

| Leg on ES ($250 a trade, 3 ES ticks) | 2025 Apr-Dec | 2026 Jan-Jun | 2026 Jul-Oct | NQ same leg 10t (Jan-Jun / Jul-Oct) |
|---|---|---|---|---|
| EMA | PF 0.44, -$870 a month | 0.66, -$527 | 1.44, $538 | 2.05 $1,065 / 3.33 $914 |
| MACD | 1.28, $349 | 0.75, -$278 | 0.70, -$458 | 2.70 $1,031 / 1.21 $92 |
| S/R | 0.89, -$112 | 0.84, -$167 | 0.60, -$490 | 3.23 $731 / 1.62 $240 |

At the 10 ES-tick stress every leg loses everywhere (PF 0.22-0.78). ATLAS's rules are an NQ edge; ES is not a second home.

## The passer, checked (post-hoc: shown, never changes the verdict)

| Check at 10 ticks, 60% sizing | Jan-Jun-like $ / lost | Jul-Oct-like $ / lost |
|---|---|---|
| E3 on the design paths (vs today) | $481 / 12.2% ($503 / 17.6%) | $408 / 10.9% ($402 / 21.7%) |
| E3 on a second random path set (vs today on it) | $471 / 14.5% ($497 / 18.6%) | $400 / 11.7% ($389 / 23.8%) |
| Neighbour: 1 loss -> 1 micro | $457 / 10.8% | $304 / 10.9% |
| Neighbour: 3 losses -> 1 micro | $491 / 14.8% | $418 / 13.9% |

Smooth in the streak length (shorter = safer, less money), and it holds on fresh paths. Why it works where the day stop and
the pause don't: those skip trades, and ATLAS's trade after a loss is as good as any (no edge in sitting out, and MFFU's
inactivity rule punishes idling); 1 micro keeps taking the signal, so a winner still ends the streak, but a third or fourth
loss costs tens of dollars instead of a few hundred of an $887 room. It changes sizing only, so trades a week, PF and the fixed view are
the same as today.

Limits of the proof: it is a sizing rule on the Monte Carlo, the streak is updated at the end of each session (live it
would update after each trade, which can only act sooner), and 2021-25 stays a losing market for ATLAS either way.

## Is ATLAS's edge holding? (lead's add-on: fresh data to Nov 19)

**Holding.** Stored research trades to Oct 16 + the live-code replay Oct 19 - Nov 19 (research/second/atlas_more_fresh.json,
CBOE VIX appended, parity with the stored trades on Oct 7 / 13 / 15). $250 a trade, member alone; ATLAS = one position, max 2
a day (tools/atlas_edge_fresh.py -> research/second/atlas_edge_fresh.json). Last 40 sessions = Sep 25 - Nov 19.

| At 10 ticks a side (6 / 1 in the json) | Last 40 sessions | Fresh Oct 19 - Nov 19 | 2026 to Oct 16 | 2021-25 | Last 40 vs every 40-session stretch: 2026 / 2021-25 |
|---|---|---|---|---|---|
| ATLAS | 26 trades, PF 2.01, $1,568 a month | 17, PF 1.76, $1,578 | PF 2.29, $2,184 | PF 0.86, -$479 | 26th / 92nd percentile |
| EMA | 14, PF 2.62, $1,015 | 9, PF 1.86, $843 | PF 2.19, $1,064 | PF 0.75, -$433 | 29th / 94th |
| MACD | 11, PF 1.37, $333 | 6, PF 1.48, $466 | PF 2.49, $862 | PF 0.95, -$58 | 35th / 71st |
| S/R | 7, PF 2.70, $509 | 4, PF 0.78, -$110 | PF 2.68, $586 | PF 0.91, -$80 | 62nd / 89th |

Plain words: the last 40 sessions are an ordinary 2026 stretch (a quarter of 2026's stretches were weaker) and better than
9 in 10 stretches of 2021-25, even at 10 ticks. No leg is failing: MACD is the softest (PF 1.37 at 10 ticks, it was PF 1.13
in Jul-Oct too), S/R's 4 fresh trades lost $110 a month but its last 40 is PF 2.7 (4 trades are noise). No Decide card.

The phone's edge check read the eval-path run atlas_deep_zombie (data to Oct 16, eval sizing). It now reads
`atlas_fresh_fixed` (tools/atlas_edge_fresh.py save: the live ATLAS units at a fixed $250, to Nov 19; the fresh weeks have
no stored LIT trades, so the never-opposite-LIT block is not applied there). The light: **AMBER -> GREEN, last 40 sessions
R-PF 2.38 vs 2026 H1 2.82, data to Nov 19** (cuts from ATLAS's own 2021-25: GREEN above 2.18 R a week; now 2.39). LIT's half
of the file is unchanged (same windows, cuts and line).

## Files

tools/atlas_edge.py (new), tools/atlas_es.py (new, helper), research/second/atlas_edge_design.md, research/second/atlas_edge.json,
research/second/atlas_es_trades.json, tools/web_public/business/decisions.json (one new open card), tools/atlas_edge_fresh.py,
research/second/atlas_edge_fresh.json, research/runs/atlas_fresh_fixed.json, tools/edge_health.py (ATLAS_RUN), research/lab/edge_health.json,
tools/web_public/edge.json, tests/test_edge_chip.py (one pin, reason in the line). No engine file, no
live_model*.json, no second_model.json, no accounts file changed.
