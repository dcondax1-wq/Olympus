---
title: Eval sizing for a FRESH MFFU Builder 25K - room share, $ caps, first-hit, ATLAS in the eval
family: risk
date: 2026-11-17
status: adopt-candidate (the lead / owner decides; paper only; no live_model file touched). Pick - LIT only, two_week at 40% of the room to session 80, then safe_eval at 60% (= the owner-approved Builder 50K rule). The mffu_builder_25k preset today (50% to session 10, then safe_eval 30%) is worse - change the preset or override it on the new account. Rejected - room 45-60%, every $ cap, first-hit. ATLAS $250 at 20% in the eval is faster in both 2026 halves but raises 2021-25 fails and needs a new route - not tonight.
summary: Owner buys a fresh Builder 25K tonight ($1,500 target, $1,000 EOD trailing, $600 soft DLL, 20 micros, no consistency, 1 day). 23 eval sizings on the exact bot config (engine/multi_account.sizing_cfg of the mffu_builder_25k preset + override -> engine/sizing.lit_qty), 1,000 Monte Carlo paths per span, the same paths as builder-levers. Pick on H1 = LIT 40% of the room to session 80 (median 12 sessions to pass, 2-week pass/fail 47.6/0.0%, 60-session fail 2.6%; H2 12, 47.2/0.0, 1.7%), first funded payout ~Jan 5 / Jan 6 (33 / 34 sessions), $553 / $456 a month. Bigger room shares (45-60%) pass 1-3 sessions sooner but 60-session fails jump to 7-21%. $ caps $150-$400 are all slower. First-hit does nothing (the first trade is already sized by "one winner covers $1,500"). The 20-micro cap never binds (0 of ~68,000 LIT trades sized); the room share and the "one winner" size bind.
runs: none (research/lab/builder25k_eval.json, tools/money/builder25k_eval.py)
---

## For the owner (one minute)

Sessions are trading days from tomorrow, 2026-11-18. Jan-Jun 2026 / **Jul-Oct 2026 (check)**. "Fail" = the eval hits the
floor OR the room falls under $100 (stuck: 1 micro no longer fits). Payout = the median day the first funded payout is
asked for (funded = LIT + ATLAS $250, the builder-levers plan). $ a month = to you, after eval fees, 6 months.

| Eval sizing on the new 25K | Median sessions to pass | 2-week pass / fail | Fail in 60 sessions | 1st payout | $ a month |
|---|---|---|---|---|---|
| **LIT, 40% of the room to session 80 (pick, = the 50K rule)** | 12 / **12** (~Dec 3) | 47.6/0.0% / **47.2/0.0%** | 2.6% / **1.7%** | Jan 5 / **Jan 6** | $553 / **$456** |
| preset today (50% to session 10, then safe 30%) | 9 / **10** | 52.8/1.6% / **50.1/0.5%** | 1.6% / **0.5%**, but 17% / **25%** sit stuck forever | Jan 4 / **Dec 30** | $531 / **$414** |
| LIT 30% / 35% | 15 / 20 · 13 / 14 | 39/0 / 28/0 · 45/0 / 43/0 | 0-1% | Jan 6-13 | $425-543 |
| LIT 45% / 50% / 55% / 60% | 9-11 / 10-12 | 49-54% pass / 0.4-6% fail | **7-19% / 9-21%** | Jan 4-5 | $457-602 |
| LIT 50% + a $150 / $200 / $250 / $300 / $400 cap | 30 / 18 / 15 / 14 / 9 (H2 40-11) | 4-53 / 0-2% fail | 5-10% / 5-10% | Jan 5 - Feb 5 | $375-580 |
| First-hit: first trade at 50-60%, then 30-40% | = its "then" size (12-15) | = its "then" size | = its "then" size | Jan 5-11 | $434-551 |
| LIT 40% + ATLAS $250 at 20% in the eval | **7 / 9** (~Nov 26) | 61.0/0.1% / **55.6/0.0%** | 1.5% / **1.5%** | **Dec 28 / Dec 30** | $605 / **$504** |
| 2021-25 (no edge): pick / ATLAS 20% | never (pass 28% / 29% in 60) | 10.6/0.0 / 17.7/1.1 | **31.5% / 52.4%** | Jan 26 / Feb 22 | -$7 / -$8 |

In plain words:
- **Use the 50K rule on the 25K: 40% of the room, two_week to session 80.** It never failed an eval in 2 weeks in either
  2026 half and passes in about 12 trading days (about Dec 3). First payout about Jan 5-6.
- **Bigger bets are a cliff, not a slope.** 45% looks almost the same in 2 weeks, but after one loss the room is too small
  for LIT's 40-50 pt stops, so 7-9% of evals die by session 60 (40%: 2-3%). 60% kills 19-21%.
- **$ caps only slow it down.** LIT's first trade is already small (2-4 micros, because its targets are ~6x the stop).
  A cap cuts the winners that pass the eval.
- **"First-hit" changes nothing.** The first trade is sized by "one winner covers $1,500", not by the room share.
- **Today's 25K preset is worse.** It passes a little sooner but 1 in 4 evals (Jul-Oct) ends stuck at 30% sizing
  and never passes: 30% no payout in 6 months vs 19%, $414 vs $456 a month.
- **ATLAS in the eval is faster (first payout ~1 week sooner, +$50 a month) in both 2026 halves**, but in 2021-25 it fails
  52% of evals vs 32%, and the bot cannot route ATLAS onto a fresh 25K eval today (lit25 is funded-only). Not tonight.

Next (paper only):
1. Lead: set the new 25K to the pick (preset change or the account's `lit_sizing` override below), Sim-test, the owner arms.
2. Owner: buy the 25K at your real price ($63 / $43 code), add it as an extra account with the override.
3. Re-run any time: `python -X utf8 tools/money/builder25k_eval.py`

## The exact config (engine/multi_account.py, preset `mffu_builder_25k`)

Change these three values of `PRESETS["mffu_builder_25k"]["sizing"]` (everything else stays):

| key | today | pick |
|---|---|---|
| `two_week.room_f` | 0.5 | **0.4** |
| `two_week_until` | 10 | **80** |
| `safe_cap` (after_mode `safe_eval`) | 0.3 | **0.6** |

Or, without touching the preset, on the new account's entry in data/accounts.json:

    "preset": "mffu_builder_25k", "mode": "two_week",
    "lit_sizing": {"two_week": {"room_f": 0.4}, "two_week_until": 80, "after_mode": "safe_eval", "safe_cap": 0.6}

`two_week.max_usd` stays null. If a $ cap is ever wanted: the 25K scales it by 0.5 (rules.scale), so $X real = `max_usd` 2X.
The tool built every option exactly this way (multi_account.sizing_cfg on live_model.json lit_sizing), so the sim sizes
what the bot would size. The preset's day guard (1 LIT entry a day) stays; LIT never had 2 entries in a day in any span.
The funded stage (60% of the room, <= $750, a winner <= $1,000) is unchanged. The payout dates assume LIT + ATLAS $250 once
funded (builder-levers); with LIT alone funded the first payout is later (builder-levers: 45 / 44 sessions).

## 1. How it was tested

- Checked first: CLAUDE_REFERENCE "Tested and rejected", lit-builder-25k.md (2026-10-19 picked 50% / safe 30% after s10
  on H1, with "stuck" as the weak spot), builder-levers-2026-11-16.md ("LIT eval, then LIT + ATLAS $250 funded"; ATLAS in
  the eval at 30% rejected on 2021-25 fails).
- Tool: `tools/money/builder25k_eval.py` (new) on builder_levers / stack_one_account (same trades, costs $1.90 a micro +
  1 tick, sizing, funded rules, 5-session blocks, seeds 7 / 23, 1,000 paths per span). The eval step = builder_levers.GEv
  plus the real n_today (the preset's day guard) and a trade counter (first-hit).
- Base check: "LIT 40% to s80" gives the builder-levers numbers for "LIT eval; funded + ATLAS $250" exactly (33 / 34
  sessions, $553 / $456, no pay 9.7 / 18.7%).
- Pick rule: on H1, the fastest median pass whose 2-week fail is <= the base + 0.5 pt and 60-session fail <= the base + 1
  pt; then H2 must be faster too with no more fails; 2021-25 shown.
- ATLAS in the eval = stack_q: $ = min($250, 20-30% of the room, the soft day left), stops at the target.

## 2. The trades (fixed $250 a trade, real days in order, costs in)

| Trades | trades/wk H1 / H2 / 2021-25 | PF | net $ | $/month | max DD |
|---|---|---|---|---|---|
| LIT | 3.1 / 2.6 / 2.4 | 3.71 / 3.00 / 1.02 | $14,406 / $6,615 / $908 | $2,363 / $1,781 / $18 | -$1,353 / -$902 / -$9,113 |
| LIT + ATLAS $250 | 7.2 / 5.5 / 7.0 | 3.21 / 2.77 / 1.07 | $32,767 / $11,871 / $11,301 | $5,376 / $3,196 / $220 | -$1,284 / -$1,052 / -$17,544 |

The sizing does not change a trade, only how many micros.

## 3. Full results (H1 · H2 · 2021-25)

Median = over all evals (an eval not passed counts as slow; 2021-25 never reaches 50% passed). 2wk = pass / fail % in 10
sessions. f60 = fail % in 60. Seat = 1st payout sessions, $ a month after fees.

| Option | median | 2wk | f60 | 1st payout | $/mo | no pay 6m |
|---|---|---|---|---|---|---|
| preset today (50% s10, safe 30%) | 9 · 10 · - | 52.8/1.6 · 50.1/0.5 · 14.3/2.0 | 1.6 · 0.5 · 10.7 | 32 · 30 · 38 | $531 · $414 · -$4 | 14.9 · 30.2 · 93.9 |
| **40% to s80 (pick)** | **12 · 12** · - | **47.6/0.0 · 47.2/0.0** · 10.6/0.0 | **2.6 · 1.7** · 31.5 | **33 · 34** · 48.5 | **$553 · $456** · -$7 | 9.7 · 18.7 · 92.4 |
| 30% | 15 · 20 | 39.0/0.0 · 27.7/0.0 · 5.2/0.0 | 0.0 · 0.0 · 4.3 | 37 · 39 · 54 | $525 · $425 · -$9 | 11.2 · 19.2 · 94.6 |
| 35% | 13 · 14 | 44.7/0.0 · 42.5/0.0 · 7.3/0.0 | 0.9 · 0.2 · 15.5 | 34 · 35 · 55.5 | $543 · $451 · -$7 | 10.8 · 18.1 · 93.4 |
| 45% | 11 · 12 | 48.9/0.4 · 48.0/0.4 · 12.2/0.9 | 6.6 · 9.1 · 48.2 | 33 · 33 · 55.5 | $566 · $457 · -$7 | 8.9 · 19.1 · 90.6 |
| 50% | 9 · 10 | 52.8/1.6 · 50.1/0.5 · 14.3/2.0 | 10.8 · 11.1 · 55.9 | 32 · 32 · 65 | $578 · $485 · -$7 | 8.2 · 16.4 · 89.6 |
| 55% | 9 · 10 | 53.3/4.2 · 52.1/4.3 · 15.6/4.6 | 15.2 · 18.0 · 61.7 | 32 · 32 · 59 | $586 · $504 · -$8 | 8.3 · 13.8 · 88.8 |
| 60% | 9 · 10 | 53.7/6.0 · 52.8/6.2 · 16.4/7.5 | 18.6 · 20.8 · 63.6 | 32 · 32 · 54.5 | $602 · $518 · -$7 | 6.8 · 12.3 · 87.4 |
| 50% + cap $150 | 30 · 40 | 10.8/0.0 · 3.7/0.0 · 0.1/0.0 | 4.7 · 4.6 · 27.9 | 53 · 56 · 88 | $465 · $375 · -$14 | 9.7 · 18.7 · 95.9 |
| 50% + cap $200 | 18 · 26 | 29.2/0.1 · 10.4/0.0 · 1.4/0.0 | 5.9 · 7.3 · 45.2 | 40 · 46 · 76.5 | $537 · $426 · -$11 | 7.9 · 16.6 · 92.2 |
| 50% + cap $250 | 15 · 16 | 37.1/0.5 · 31.8/0.0 · 4.4/0.6 | 8.6 · 7.5 · 52.6 | 37 · 38 · 64 | $548 · $471 · -$12 | 8.2 · 15.9 · 92.7 |
| 50% + cap $300 | 14 · 16 | 41.0/0.8 · 34.6/0.3 · 6.5/1.4 | 9.9 · 9.8 · 55.5 | 36 · 37.5 · 67 | $552 · $456 · -$11 | 9.5 · 16.4 · 92.0 |
| 50% + cap $400 | 9 · 11 | 53.3/1.5 · 49.8/0.1 · 12.0/2.4 | 9.9 · 10.4 · 55.6 | 33 · 33 · 70.5 | $580 · $481 · -$9 | 7.7 · 16.3 · 90.2 |
| 60% + cap $300 | 13 · 16 | 41.3/4.8 · 34.6/1.4 · 6.7/3.2 | 17.2 · 18.4 · 62.2 | 36 · 38 · 66 | $567 · $480 · -$14 | 8.3 · 12.9 · 91.7 |
| 60% + cap $400 | 9 · 10 | 54.0/5.6 · 50.8/6.5 · 13.3/5.5 | 17.8 · 20.2 · 63.4 | 31 · 33 · 56 | $604 · $508 · -$8 | 6.9 · 12.9 · 88.1 |
| first-hit 60% then 40% | 12 · 13 | 47.5/0.0 · 45.7/0.0 · 13.0/0.3 | 2.8 · 1.9 · 32.5 | 33 · 34 · 46 | $551 · $450 · -$7 | 10.0 · 19.7 · 92.3 |
| first-hit 60% then 30% | 14 · 18 | 41.5/0.0 · 38.0/0.0 · 9.6/0.0 | 0.0 · 0.0 · 5.1 | 36 · 37 · 50 | $535 · $434 · -$8 | 10.7 · 20.6 · 94.7 |
| first-hit 50% then 35% | 13 · 13 | 45.1/0.0 · 46.3/0.0 · 9.4/0.0 | 0.9 · 0.0 · 16.5 | 34 · 34 · 50 | $545 · $454 · -$6 | 10.6 · 18.7 · 92.9 |
| first-hit 50% then 40% | 12 · 12 | 47.5/0.0 · 47.6/0.0 · 11.8/0.1 | 2.8 · 1.7 · 32.1 | 33 · 34 · 46 | $551 · $450 · -$7 | 10.0 · 19.7 · 91.9 |
| first-hit 2 trades 50% then 40% | 12 · 11 | 47.5/0.0 · 48.4/0.0 · 13.0/0.2 | 3.0 · 2.0 · 32.3 | 33 · 33 · 46 | $548 · $450 · -$8 | 10.2 · 20.0 · 91.9 |
| LIT 40% + ATLAS $250 at 20% | 7 · 9 | 61.0/0.1 · 55.6/0.0 · 17.7/1.1 | 1.5 · 1.5 · **52.4** | 28 · 30 · 67 | $605 · $504 · -$8 | 9.1 · 15.2 · 90.9 |
| LIT 40% + ATLAS $250 at 30% | 7 · 9 | 64.2/0.6 · 56.2/0.0 · 20.6/5.4 | 4.5 · 6.1 · 69.4 | 27 · 30 · 59 | $618 · $511 · -$8 | 8.2 · 14.3 · 87.7 |
| LIT 50% + ATLAS $250 at 20% | 7 · 8 | 61.6/1.5 · 60.3/1.3 · 19.1/5.5 | 9.1 · 8.9 · 66.0 | 28 · 29 · 55 | $616 · $523 · -$10 | 7.6 · 13.1 · 89.5 |

- **Picked on H1 (LIT only, routable tonight):** 40% to s80. Every faster LIT-only option raises the 60-session fail
  beyond +1 pt (45%: +4.0; 50%: +8.2), every slower one is slower. First-hit 50%->40% and "2 trades" are within noise of
  the pick (0 to 1 session, +0.2-0.4 pt fails): no gain, not worth a new rule.
- **H2 check:** the same ordering holds (45%: 9.1% vs 1.7% fails; caps slower; first-hit equal).
- **Fastest overall on H1 without more 2026 fails: LIT 40% + ATLAS $250 at 20%** (median 7, 2-week pass 61%, 60-session
  fails 1.5% vs 2.6%); H2 also better (9 vs 12, 55.6% vs 47.2%, 1.5% vs 1.7%; first payout Dec 30 vs Jan 6, +$48 a month).
  But 2021-25: 60-session fails 52.4% vs 31.5% and first payout 67 vs 48.5 sessions; the $ is the same (-$8 vs -$7). Under
  the "other strategies: both 2026 halves AND 2021-25" rule it does not pass, and it needs a build (an eval-stage ATLAS
  lane on an extra account; engine/lit25.py is funded-only). Owner yes/no for a later eval, not for tonight.
- **Preset today vs the pick:** faster to pass (9-10 vs 12) because 50% bets more, but after session 10 safe_eval at 30%
  leaves 17% (H1) / 25% (H2) of evals stuck between $100 and ~$300 of room, never passing and never failing (2-week fails
  1.6% / 0.5% vs 0.0% / 0.0%). The 2026-10-19 pick (lit-builder-25k.md) measured only the 2-week window.

## 4. Does the 20-micro cap bind? No.

Counted on 300 paths x 60 sessions per span, every LIT signal, at the pick (and 45-60%, the caps, first-hit, ATLAS):

| | H1 | H2 | 2021-25 |
|---|---|---|---|
| LIT stop: 10th / median / 90th pct | 21.9 / 44.2 / 73.1 pts | 30.0 / 51.6 / 80.3 pts | 19.5 / 38.2 / 69.2 pts |
| 20 micros at the median stop would risk | $1,818 | $2,113 | $1,578 |
| trades where 20 micros was the limit | **0 of 3,090** | **0 of 2,287** | **0 of 4,277** |
| what set the size: "one winner covers what is left" / 40% of the room | 45% / 55% | 40% / 60% | 25% / 75% |
| signals skipped because 1 micro does not fit the room | 20.7% | 33.1% | 29.6% |
| ... of those with $700+ of room | 0 | 0 | 0 |

- The 40% room share ($400 on a fresh $1,000 room) binds long before 20 micros (the $600 soft daily loss never set the size). On a fresh
  eval LIT bets 2-9 micros (median 3).
- The wide-stop problem is real, but it is the ROOM, not the 20 micros. After losses (room $115-$300) one micro of a 40-80
  pt stop ($82-$162 risk) no longer fits 40% of the room, so the bot skips. Those evals are the "stuck" ones. Bigger room
  shares skip less but get there faster. That is why 45%+ fails more.
- The same holds for every option tested (cap20 = 0 everywhere).

## 5. Honest limits

- One seed pair (7 / 23), 1,000 paths: gaps under ~1 session, ~1 pt or ~$20 a month are noise.
- H2 has only 40 LIT trades. 2021-25 has no LIT edge (PF 1.02): every option there is about $0 a month.
- "Stuck" (room < $100) is counted as a fail. MFFU would not close it, but the bot can no longer trade it.
- The payout dates assume the funded 25K gets LIT + ATLAS $250. That route exists only for ATLAS's own funded 25K
  (engine/lit25.py, OFF). For this new 25K it is a build for later.
- ATLAS's own 25K (passing to funded), Zlarior and this 25K would all carry LIT signals: a LIT losing week hits them all.
- Nothing live changed: no live_model*.json, preset or engine file edited. The lead wires the config; the owner arms.
