---
title: ATLAS funded 25K - one trade a day (2026-10-31) - fewer trades on the funded account pays the owner LESS; the second trade of the day is part of the money
family: risk
date: 2026-10-31
status: rejected (no change) - funded max 1 a day loses slot $ in every span (H1 $454 vs $568, H2 $275 vs $382, 2021-25 -$3 vs -$2 a month) and loses even to a random 1-a-day control; the H1 pick (up to 3 a day) adds +$44 in H1 but exactly $0 in H2 on all 4 path seeds
summary: Owner 2026-10-31 "keep building those strategies" - does the FUNDED ATLAS 25K pay the owner more with a day limit of one trade (the day's first ATLAS signal) instead of two? Eval unchanged (today's ATLAS), so only the whole-slot money can move (tools/atx_edge.slot - eval -> funded -> MFFU payouts -> a new $63 eval, 300 paths x 126 sessions). Trade-count rules were tested on the eval path before (atlas-confluences.md), never on the funded account's payouts. Picked on 2026 H1, checked on H2 and 2021-25, random 1-a-day control (4 seeds), neighbours max 3 / max 4, 4 path seeds.
runs: atxd_max1, atxd_max3, atxd_today
---

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

**Eval (unchanged in every row, today's ATLAS on the Builder 25K):** 2-week pass / dead H1 65.5 / 0.8, H2 43.5 / 0.0,
2021-25 24.6 / 26.2; eval-path $1,394 / $547 / -$63 a month less fees; 4.4 / 3.3 / 5.2 candidate trades a week
(2.1 / 1.6 / 2.9 taken).

**Funded trades on the real sessions (one path from each span's first session; the funded stretches differ by variant):**

| Funded trades | H1: n, PF, R per $ risked, net, max DD | H2 | 2021-25 | Real-path slot $/mo H1 / H2 |
|---|---|---|---|---|
| Today | 86, 2.94, +0.867, +$10,947, -$1,032 | 38, 2.96, +0.657, +$4,113, -$1,175 | 382, 0.94, -0.040, -$2,405, -$10,305 | $596 / $414 |
| Max 1 a day | 72, 3.17, +0.941, +$9,823, -$978 | 32, 2.45, +0.491, +$2,489, -$724 | 443, 1.10, +0.059, +$3,763, -$5,069 | $476 / $177 |
| Max 3 a day | 73, 3.43, +0.970, +$10,559, -$1,032 | = today | 484, 0.98, -0.016, -$1,173, -$9,596 | $596 / $414 |

2021-25 is the old regime where ATLAS barely breaks even; max 1 a day looks better there per trade, but its slot $ is
the same (-$3 vs -$2 a month): the account almost never gets funded long enough for it to matter.

## Method

- **Simulator:** `tools/atx_edge.slot` (whole 25K slot; 300 block-bootstrap paths x 126 sessions, 5-session blocks, seed
  23 = the pick; seeds 5 / 11 / 41 = robustness), `tools/atx_edge.real_slot` for the trades (one path on the real
  sessions). Costs in ($1.90 a micro + slippage, as `tools/second_mix`). TradingView CME NQ1! data only.
- **Change:** the funded stage's day limit only (`second_mix.play_day` max_day 1 / 3 / 4; live and today = 2). The eval
  stage is untouched, so eval numbers are today's by construction.
- **Pick rule:** best H1 slot $ of max 1 / max 3 (max 4 = neighbour). **Gate:** slot $ up in H1, H2 and 2021-25.
- **Control:** keep one RANDOM signal of the day (seeded by date, 4 seeds) instead of the first, so "1 a day" had to beat
  "any 1 a day".

## Files

- Code: `tools/atx_funded_day.py` (`run` = every variant + seeds -> `research/second/atx_funded_day.json`; `save` = runs).
- Runs: `research/runs/atxd_today.json`, `atxd_max1.json`, `atxd_max3.json` (trades = the slot on the real sessions,
  eval + funded, tagged `atlas-eval:<member>` / `atlas-funded:<member>`).

Paper research only. Nothing in `engine/`, `second_model.json`, `live_model*.json` or `data/` was changed.
