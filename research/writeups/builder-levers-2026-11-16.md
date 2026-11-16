---
title: Three MFFU Builder levers for money sooner - a parallel fresh eval, the second Builder 25K, the funded payout policy
family: risk
date: 2026-11-16
status: adopt-candidate (owner decides; paper only) - buy a fresh Builder 50K now and run it next to Zlarior's hole eval (better in both 2026 halves); same for ATLAS's 25K ($43). Second Builder 25K - LIT eval, then LIT + ATLAS $250 once funded (beats the LIT 25K copy in both halves). Rejected - rescue sizings for a deep-hole eval, every payout-request policy and the best-day day stop (no gain in both halves).
summary: Owner 2026-11-16 - money sooner, MFFU only. Same trades, costs, sizing and Monte Carlo paths as stack-one-account (LIT live two_week / UP50, ATLAS account-B need size + zombie rule, BLITZ account C; 1,000 paths of 126 sessions per half, 5-session blocks). 1) EVAL RESCUE - Zlarior's hole ($1,145 room, $3,687 to go, 2026-11-07 numbers) passes at a median 14-15 sessions (2-week pass 25-29%); a fresh 50K passes at 8-9 (48%). Buying a fresh Builder 50K now and running both on the same signal (first pass kept) moves the first funded payout from 53 / 50 to 46.5 / 44 sessions (about Feb 1 / Jan 27 -> Jan 21 / Jan 19) and the seat from $739 / $709 to $777 / $754 a month after the extra $91.80. It pays at every hole with room <= $1,145 tested and not at room $1,500. ATLAS 25K the same way ($43) - 35 / 56 -> 31 / 47 sessions, $599 / $381 -> $617 / $412. Rescue sizings - bigger (55-70% of the room) pass sooner but fail 18-30% of hole evals in 2 weeks; smaller (25-30%) are slower: rejected. 2) The second Builder 25K - LIT eval then LIT + ATLAS $250 funded gives the first payout in 33 / 34 sessions and $553 / $456 a month vs the LIT 25K copy's 45 / 44 and $346 / $298, daily correlation with ATLAS's own 25K 0.52 / 0.36; ATLAS + BLITZ is as rich in H1 but 0.82-0.84 alike to ATLAS's 25K and fails 37% of 2021-25 evals in 2 weeks. 3) Funded 50K payout engine - ask $500 asap / $1,000 / $2,000 / cycle-timed and a best-day-aware day stop move the first payout by at most 1-2 sessions and the $ by under 2%; none is better in both halves on both - keep today's ask $1,500. Combined (fresh parallel eval + ATLAS $500 on the funded 50K) - first payout 33 / 33 sessions = about Jan 4, $1,197 / $1,206 a month. 2021-25 pays about $0 on every option.
runs: none (research/lab/builder_levers.json)
---

## For the owner (one minute)

Sessions are trading days from tomorrow, 2026-11-17. "1st payout" = the median day the first payout is requested (the money
lands about 3 trading days later). $ a month = to you, after every eval fee, 6 months. Jan-Jun 2026 / **Jul-Oct 2026 (check)**.

| What | 1st payout (sessions, date) | $ a month | No payout in 6 months | Verdict |
|---|---|---|---|---|
| **Zlarior today** (keep the hole eval, LIT alone funded) | 53 / **50** (~Feb 1 / Jan 27) | $739 / **$709** | 8.9% / 11.0% | baseline |
| **Zlarior + a fresh Builder 50K now ($91.80), both trade, first pass kept** | 46.5 / **44** (~Jan 21 / Jan 19) | $777 / **$754** | 7.8% / 9.2% | **better in both halves** |
| Zlarior hole at a bigger "rescue" size (55-70% of the room) | 46-47 / **43-44** | $777-796 / **$755-766** | 7-10% | rejected: 18-30% of these evals fail in 2 weeks (today 2-4%) |
| Zlarior: fresh 50K now + ATLAS $500 on the funded 50K | 33 / **33** (~Jan 4) | $1,197 / **$1,206** | 5.1% / 7.2% | both levers together |
| ... + BLITZ $300 too on the funded 50K | 31 / **30** (~Dec 30) | $1,308 / **$1,347** | 4.6% / 5.7% | |
| **ATLAS 25K today** (keep the hole) | 35 / **56** (~Jan 6 / Feb 4) | $599 / **$381** | 3.3% / 10.1% | baseline |
| **ATLAS + a fresh Builder 25K now ($43)** | 31 / **47** (~Dec 30 / Jan 22) | $617 / **$412** | 3.5% / 8.8% | **better in both halves** |
| **2nd Builder 25K ($63): LIT 25K copy** | 45 / **44** | $346 / **$298** | 14.4% / 23.3% | the old plan |
| **2nd Builder 25K: LIT eval, then LIT + ATLAS $250 once funded** | 33 / **34** (~Jan 4 / Jan 5) | $553 / **$456** | 9.7% / 18.7% | **better in both halves, no extra eval fails** |
| 2nd Builder 25K: LIT + ATLAS $250 in the eval too | 28 / **30** (~Dec 24 / Dec 29) | $618 / **$511** | 8.2% / 14.4% | faster, but 0.6% / 0% fail in 2 weeks (5.4% in 2021-25) |
| Funded 50K: ask $500 asap / $1,000 / $2,000 / cycle-timed, best-day day stop | within 1-2 sessions of today | within 2% of today | same | rejected: no gain in both halves |
| 2021-25 (no edge), any option | 66-88 | -$9 to +$3 | 90-93% | a 2026 bet |

In plain words:
- **Zlarior's eval is in a hole, so a fresh eval is the faster horse.** The hole has $1,145 of room and needs $3,687.
  A fresh 50K has $2,000 of room and needs $3,000, and the live size is 40% of the room. So the fresh one passes at about
  9 trading days, the hole at about 15. Running both costs $91.80 and brings the first payout about 6 trading days
  sooner, in both 2026 halves. MFFU allows up to 10 evals but funds only 1 Builder 50K, so the first one to pass is kept.
- **ATLAS: the same, for $43.**
- **Bigger "rescue" bets on the hole do not work.** They pass sooner, but 1 in 5 to 1 in 3 of those evals blows up
  within 2 weeks.
- **Second 25K: LIT on the eval, then LIT + ATLAS once funded.** That gets the first payout about 11 trading days sooner
  than a plain LIT copy, and about $150-200 a month more. It also moves less like ATLAS's own 25K (correlation 0.36-0.52,
  against 0.92 for a 2nd ATLAS copy).
- **How and when you ask for the payout does not matter.** The 2-days-a-cycle rule and the 50% best-day rule set the
  pace. Keep today's ask at $1,500.

Next (paper only, nothing changed):
1. Yes / no: buy a fresh Builder 50K now (and a 25K for ATLAS at $43). The bot copies Zlarior's trades onto the new eval
   (the fleet `--plan mffu_builder_50k` copy, Sim-tested); the lead wires it and the owner arms it himself.
2. Send me today's real numbers for both evals, and I re-check:
   `python -X utf8 tools/money/builder_levers.py --z-room 1145 --z-togo 3687 --a-room 822 --a-togo 1678`
3. Yes / no: a second Builder 25K: "LIT eval, then + ATLAS $250 once funded" (it needs the stack-one-account funded route
   built first).

## 1. What was tested and how

- **Already tested, not redone.** Checked first: `CLAUDE_REFERENCE.md` "Tested and rejected", `eval-cost.md`,
  `eval-game.md`, `payout-policy.md`, `second-mix.md` and `stack-one-account-2026-11-16.md`.
  - eval-game said "a second account on the same trades buys no speed". That was about two FRESH evals bought together.
    Here one eval is already in a hole, and the second one is fresh.
  - The ask line $1,000 / $2,000 was rejected on the owner's copied stack in payout-policy. Here it is re-checked on a
    funded 50K that carries ATLAS (+ BLITZ), so there are 2+ winning days a week. Cycle-timed asks and the best-day day
    stop are new.
  - Rapid EOD was not touched (another helper).
- **Tool.** `tools/money/builder_levers.py` reuses the stack_one_account / account4_sim / uprisk loaders and accounts:
  - `GEv` = `stack_one_account.Ev`, from any start state. Checked: from a fresh start it gives exactly the same eval
    numbers (H1 47.5/0.8, median 9; H2 47.3/0.2, median 9).
  - `GF` = `uprisk.Funded` with per-strategy sizes, a request policy and a day stop. Checked: the funded LIT alone and
    LIT + ATLAS $500 numbers match stack-one-account exactly (26 / 23.5 and 17 / 15 sessions; $929 / $915 and
    $1,232 / $1,214).
- **MFFU funded rules.** These are uprisk.Funded, matched bit for bit with engine/sizing + engine/funded_life:
  - Payouts: buffer $2,100 / $1,100; requests $500-$2,000 / $250-$1,000; 80%; 5 payouts.
  - Cycle: best day at most 50% of the cycle; 2 traded days a cycle; 48 h wait before the first payout.
  - Floor: locked at +$100 after the first payout.
  - The 25K: UP25 (60% of the room, up to $750, a winner up to $1,000).
- **ATLAS on a 25K eval.** engine/account_b need size through tools/atlas.q_variant: two_week to session 10, then
  safe_eval at 30% of the room. The zombie-eval rule is on: a last bullet of 1 micro within 80% of the room, and the eval
  is given up under $200 of room.
  - This is a stand-in for the second_account_b executor. Fresh-eval 2-week pass is 64% / 44%, against the published
    57% / 35% (a different window method). The ATLAS numbers are read side by side, on the same model.
- **Seat.** Evals (1, or 2 in parallel on the same signal) -> 2 sessions of paperwork -> funded -> lost or 5 payouts ->
  a fresh eval.
  - Parallel: the first eval to pass is kept and the other is dropped (MFFU funds 1 Builder 50K).
  - A failed or stuck eval is dropped. With none left, a fresh one is bought.
- **Monte Carlo.** 1,000 paths x 126 sessions per half (seed 23), eval checks 1,000 x 60 (seed 7), threshold grid 500
  paths. 5-session blocks, and every option runs on the same paths. Costs: $1.90 a micro + 1 tick.
- **Start state.** Taken as arguments; the defaults are the 2026-11-07 numbers.
  - Zlarior: balance -$687 vs start, floor -$1,832, session 20.
  - ATLAS: -$178, floor -$1,000, session 20 assumed.
  - Both are probably stale: re-run with today's numbers.

## 2. The trades themselves (fixed $ a trade, the real days in order, costs in)

| Trades | trades/wk H1 / H2 / 2021-25 | PF | net $ | $/month | max DD |
|---|---|---|---|---|---|
| LIT, $500 a trade (Zlarior, every eval option) | 3.1 / 2.6 / 2.4 | 3.49 / 2.71 / 1.02 | $31,246 / $13,767 / $1,961 | $5,126 / $3,707 / $38 | -$3,271 / -$2,228 / -$19,725 |
| ATLAS, $250 a trade (ATLAS 25K options) | 4.1 / 3.0 / 4.6 | 2.92 / 2.55 / 1.08 | $18,362 / $5,256 / $10,393 | $3,012 / $1,415 / $203 | -$1,062 / -$876 / -$11,403 |
| LIT $500 + ATLAS $500 (funded 50K) | 7.2 / 5.5 / 7.0 | 3.12 / 2.74 / 1.07 | $72,901 / $27,304 / $24,948 | $11,960 / $7,351 / $486 | -$3,017 / -$2,480 / -$37,025 |
| LIT $500 + ATLAS $500 + BLITZ $300 | 15.7 / 12.3 / 15.5 | 2.63 / 2.52 / 1.06 | $80,372 / $32,584 / $31,191 | $13,186 / $8,773 / $608 | -$2,950 / -$2,480 / -$33,476 |

The levers do not change a trade. They change which account trades it, at what size, and when the money is asked for.

## 3. Lever 1 - eval rescue (Zlarior 50K, ATLAS 25K)

### Zlarior (room $1,145, $3,687 to go)

| Option | eval: 2-wk pass / fail %, median (the hole eval) | seat: pass in 60 % / median | 1st payout (sessions, date) | no pay 6m | $/mo after fees | fees 6m |
|---|---|---|---|---|---|---|
| continue (today) | 29.0/3.7, 14 · **25.3/2.4, 15** · 3.2/5.0, 20 | 90.3/19 · **88.5/21** · 29.8/61 | 53 · **50** · 88 (Feb 1 / **Jan 27**) | 8.9 · **11.0** · 92.5 | $739 · **$709** · -$5 | $41 / $45 |
| **+ fresh eval now** | fresh: 48.5/0.5, 9 · **48.2/0.4, 8** · 11.4/0.5, 14 | 94.2/12 · **92.1/11** · 39.5/46 | **46.5 · 44 · 77** (Jan 21 / **Jan 19**) | 7.8 · **9.2** · 90.7 | **$777 · $754** · -$9 | $126 |
| restart fresh (drop the hole) | (fresh only) | 94.5/12 · 92.5/11 · 40.3/45 | 46 · 44 · 78 | 7.7 · 9.6 · 90.6 | $779 · $753 · -$9 | $127 |
| rescue room 25% | 18.3/0.0, 20 · 8.6/0.0, 24 | 80.9/26 · 73.4/31 | 59 · 62 · 100 | 12.9 · 16.5 | $671 · $602 | |
| rescue room 30% | 25.5/0.3, 18 · 16.0/0.0, 21 | 84.6/23 · 79.1/26.5 | 56 · 56 · 90 | 11.5 · 14.4 | $696 · $646 | |
| rescue room 55% | 36.1/**18.4**, 10 · 34.6/**19.1**, 10 | 94.0/15 · 93.7/15 | 47 · 44 · 69.5 | 8.3 · 9.9 | $777 · $755 | |
| rescue room 70% | 41.5/**27.1**, 7 · 37.2/**29.7**, 8 · 7.0/**44.0** | 94.9/12 · 94.5/14 | 46 · 43 · 75 | 7.0 · 9.7 | $796 · $766 · $3 | |

- **Fresh eval now.** Better than continuing in both halves:
  - first payout 6.5 / 6 sessions sooner;
  - +$38 / +$45 a month after the extra $91.80;
  - fewer 6-month no-pays.
  It is a cheap option on the hole, and it adds no eval risk. Restart-fresh (abandon the hole) gives the same numbers,
  because the fresh eval wins the race almost every time. Keeping the hole running costs nothing extra.
- **Rescue sizes.**
  - Bigger sizes (55-70%) reach the same speed as the fresh eval. But the hole eval then fails in 2 weeks 18-30% of
    the time (2021-25: 23-44%). Rejected on the 2-week-fail rule. It would also break the owner-approved 40% room rule.
  - Smaller sizes (25-30%) are slower and pay less.

### ATLAS 25K (room $822, $1,678 to go)

| Option | hole eval 2-wk pass / fail %, median | seat median pass | 1st payout | no pay 6m | $/mo after fees |
|---|---|---|---|---|---|
| continue (today) | 37.9/6.1, 12 · **13.0/0.2, 23** · 11.7/29.1, 9 | 12 · **25** · 28 | 35 · **56** · 52 (Jan 6 / **Feb 4**) | 3.3 · **10.1** · 79.4 | $599 · **$381** · $21 |
| **+ fresh 25K now ($43)** | fresh: 64.3/11.7, 6 · **44.0/6.1, 10** | 7 · **13** · 22 | **31 · 47** · 47 (Dec 30 / **Jan 22**) | 3.5 · **8.8** · 78.8 | **$617 · $412** · $17 |
| restart fresh | | 7 · 12 · 19 | 30 · 46 · 46 | 3.7 · 8.6 · 78.1 | $621 · $414 · $16 |
| rescue: need size kept (two_week to 80) | 55.9/**16.3**, 7 · 37.3/**10.3**, 10 · 17.6/**62.4** | 8 · 13 · 19 | 30 · 45 · 43 | 4.2 · 8.1 · 78.1 | $624 · $430 · $24 |
| rescue: safe cap 50% | 45.1/**25.9**, 6 · 20.3/6.8, 16 | 9 · 21 | 32 · 51 | 4.0 · 9.1 | $618 · $396 |
| rescue: safe cap 20% | 23.3/1.0, 17 · 6.4/0.0, 27 | 18 · 29 | 40 · 59 | 3.4 · 9.4 | $576 · $372 |
| rescue: no last bullet (zombie rule off) | 37.6/1.1, 12 · 13.0/0.0, 21 | 14 · 28 | 37 · 59 | 4.1 · 15.6 | $576 · $342 |

- **Fresh 25K now.** Better in both halves: 4 / 9 sessions sooner, +$18 / +$31 a month after the $43.
- **Rescue sizes.** "Need size kept" is about as fast, but it fails 10-16% of hole evals in 2 weeks (62% in 2021-25).
  Rejected.
- **The zombie rule stays on.** Without the last bullet the hole is much slower in H2.

### Threshold table: when does a parallel fresh eval pay?

"Pays" means the first payout comes sooner AND the $ a month (after the extra fee) is no lower, in BOTH 2026 halves.
500 paths each.

Builder 50K (fresh $91.80). Each cell = sessions to the first payout, continue -> with a fresh eval (H1 / H2).

| room above the floor \ $ still to the target | $1,500 | $2,500 | $3,000 | $3,687 | $4,200 |
|---|---|---|---|---|---|
| $300 | - | - | 56->46 / 54->44 **pays** | 57->46 / 55->44 **pays** | 58->46 / 56->44 **pays** |
| $600 | - | 52->46 / 51->44 **pays** | 53->46 / 52->44 **pays** | 55->46 / 54->44 **pays** | 56->46 / 57->44 **pays** |
| $900 | - | 52->47 / 49.5->44 **pays** | 53->46.5 / 51->44 **pays** | 53->46 / 53->44 **pays** | - |
| $1,145 | - | 49->46 / 48->44 **pays** | 52->46 / 50->44 **pays** | **53->46 / 52->44 pays (Zlarior)** | - |
| $1,500 | 42->42 / 41->41 no | 48->46 / 44->44 no ($ lower) | 48->46 / 47->44 no ($ lower H1) | - | - |

"-" = that combination cannot happen: the floor can only sit between start - $2,000 and start + $100.

Builder 25K (fresh $43):

| room \ to go | $900 | $1,300 | $1,678 | $2,100 |
|---|---|---|---|---|
| $250 | - | 32->30 / 50->46 pays | 33->30 / 52->47 pays | 34->30 / 54->47 pays |
| $400 | - | 33->30 / 51->46 pays | 34->30 / 55->47 pays | 37->30 / 59.5->47 pays |
| $600 | 31->29 / 47->45 pays | 34->30 / 52->47 pays | 36->30 / 56->47 pays | - |
| $822 | 31->29 / 47->45 pays (+$0) | 33->30 / 51.5->47 pays | **35->30 / 56->47 pays (ATLAS)** | - |

Rule of thumb:
- **50K: buy a fresh one when the room is under about $1,200**, whatever is still to go. With $1,500+ of room the hole is
  as good as fresh.
- **25K at $43: any hole pays.** Below about $1,300 to go and $800+ of room it is a coin flip.

## 4. Lever 2 - the second Builder 25K slot (fresh, $63)

| Mix on the new 25K | trades/wk (fixed $) | PF | $/mo fixed $ | max DD | eval median, 2-wk pass/fail % | 1st payout (from buying) | no pay 6m | slot $/mo after fees | corr. with ATLAS's 25K | both pay $0 in 6m | the two 25Ks together $/mo |
|---|---|---|---|---|---|---|---|---|---|---|---|
| LIT 25K copy | 3.1 / 2.6 / 2.4 | 3.71 / 3.00 / 1.02 | $2,363 / $1,781 / $18 | -$1,353 / -$902 | 9, 47.6/0.0 · 8, 47.2/0.0 · 14, 10.6/0.0 | 45 / 44 / 69 | 14.4 / 23.3 / 94.1 | $346 / $298 / -$12 | 0.10 / -0.02 | 0.3 / 2.5 | $945 / $679 |
| **LIT eval; funded + ATLAS $250** | 7.2 / 5.5 / 7.0 (funded) | 3.21 / 2.77 / 1.07 | $5,376 / $3,196 / $220 | -$1,284 / -$1,052 | = LIT copy | **33 / 34** / 48.5 | 9.7 / 18.7 / 92.4 | **$553 / $456** / -$7 | 0.52 / 0.36 | 0.8 / 2.5 | $1,151 / $837 |
| LIT + ATLAS $250 (eval too) | 7.2 / 5.5 / 7.0 | 3.21 / 2.77 / 1.07 | $5,376 / $3,196 / $220 | -$1,284 / -$1,052 | 6, 63.8/0.6 · 8, 55.8/0.0 · 6, 20.2/**5.4** | 28 / **30** / 59 | 8.2 / 14.4 / 87.7 | $618 / $511 / -$8 | 0.61 / 0.49 | 0.6 / 2.9 | $1,217 / $892 |
| ATLAS + BLITZ $150 | 12.5 / 9.7 / 13.2 | 2.35 / 2.04 / 1.07 | $3,976 / $2,082 / $276 | -$1,005 / -$1,079 | 6, 66.9/3.7 · 9, 49.8/1.6 · 6, 25.1/**37.1** | 27 / 37 / 41 | 4.4 / 7.6 / 77.9 | **$664** / $518 / $9 | **0.82 / 0.84** | 0.8 / 3.8 | $1,262 / $899 |
| LIT + Asia slot | 4.9 / 4.1 / 3.2 | 2.86 / 2.66 / **0.92** | $2,537 / $2,334 / -$113 | -$1,260 / -$848 | 8, 50.0/0.0 · 7, 54.7/0.0 · 13, 9.9/1.0 | 39 / 32 / 73.5 | 14.2 / 11.1 / 95.0 | $385 / **$526** / -$21 | 0.08 / -0.05 | 0.5 / 1.0 | $984 / $907 |
| 2nd ATLAS copy | 4.1 / 3.0 / 4.6 | 2.92 / 2.55 / 1.08 | $3,012 / $1,415 / $203 | -$1,062 / -$876 | 6, 64.3/**11.7** · 10, 44.0/6.1 · 5, 23.0/**52.0** | 30 / 46 / 46 | 3.7 / 8.6 / 78.1 | $614 / $409 / $5 | 0.92 / 0.93 | 2.3 / 6.2 | $1,213 / $790 |

ATLAS's own 25K on the same paths, from its hole: first payout 35 / 56 sessions, $599 / $381 a month.

- **Picked on H1.**
  - ATLAS + BLITZ makes the most $ in H1 ($664). In H2 it drops to 3rd ($518, against LIT + Asia's $526).
  - Its first payout in H2 is 37 sessions, the slowest of the ATLAS mixes.
  - It is 0.82-0.84 alike to ATLAS's own 25K, so the two accounts would boom and bust together.
  - It fails 37% of 2021-25 evals in 2 weeks.
  - Not picked.
- **LIT eval, then LIT + ATLAS $250 once funded.** Beats the LIT 25K copy in both halves:
  - first payout 33 / 34 sessions vs 45 / 44;
  - $553 / $456 vs $346 / $298 a month;
  - the same eval, so no extra eval fails;
  - correlation with ATLAS's 25K 0.36-0.52.
  - This is the 25K version of stack-one-account's "LIT eval, funded + ATLAS" (already the Builder 50K pick).
- **ATLAS in the 25K eval too.** About 4-5 sessions sooner and about $55-65 a month more. But 2-week fails are 0.6% in H1
  (the noise line is +0.5) and 5.4% in 2021-25 (LIT copy 0%). Same verdict as on the 50K: not in the eval.
- **LIT + Asia slot.** Nicely decorrelated, but it loses money in 2021-25 (PF 0.92). The PC route blocks Asia entries
  (second-mix.md). Not picked.

## 5. Lever 3 - funded Builder 50K payout engine

Funded only, 6 months from the first funded session (1,000 paths). Each cell = first payout median sessions / no payout
in 6 months / $ a month to you / payouts.

| Funded mix and policy | Jan-Jun | **Jul-Oct** | 2021-25 |
|---|---|---|---|
| LIT alone, ask $1,500 (today) | 26 / 5.5% / $929 / 3.5 | **23.5 / 7.2% / $915** | 43 / 79% / $66 |
| LIT alone, ask $500 asap | 26 / 5.5% / $926 | 23 / 7.1% / $913 | 43 / 79% / $66 |
| LIT alone, ask $2,000 | 28 / 5.7% / $926 | 26 / 7.5% / $907 | 45.5 / 81% / $61 |
| **LIT + ATLAS $500, ask $1,500** | **17 / 3.7% / $1,232 / 4.6** | **15 / 5.3% / $1,214** | 21 / 81% / $76 |
| LIT + ATLAS $500, ask $500 asap | 17 / 3.7% / $1,231 | 14 / 5.3% / $1,202 | 21 / 81% / $76 |
| LIT + ATLAS $500, cycle-timed | 17 / 3.7% / $1,231 | 14 / 5.3% / $1,202 | 21 / 81% / $76 |
| LIT + ATLAS $500, ask $2,000 | 17 / 3.7% / $1,233 | 16 / 5.3% / $1,219 | 21 / 81% / $75 |
| LIT + ATLAS $500, ask $1,500 + best-day stop $1,000 | 16 / 4.4% / $1,218 | 15 / 5.4% / $1,214 | 20 / 83% / $68 |
| LIT + ATLAS $500, ask $1,500 + best-day stop $500 | 16 / 4.8% / $1,208 | 15 / 5.5% / $1,213 | 21 / 83% / $68 |
| LIT + ATLAS $500 + BLITZ $300, ask $1,500 | 15 / 3.8% / $1,257 / 4.7 | 13 / 4.5% / $1,242 | 19 / 81% / $78 |
| ... ask $500 asap / $1,000 / cycle-timed | 14 / 3.8% / $1,254-1,255 | 13 / 4.5% / $1,236-1,238 | 19 / 81% / $78 |
| ... ask $2,000 | 15 / 3.8% / $1,260 | 14 / 4.5% / $1,250 | 19 / 81% / $78 |
| ... best-day stop $500 / $1,000 | 14 / 4.4-4.8% / $1,241-1,252 | 13 / 4.4-4.6% / $1,234-1,240 | 18-19 / 82-83% / $70-74 |

The policies:
- **Ask $X:** a request goes in at the first eligible session once at least $X is above the buffer, and it asks for all
  of it, up to $2,000.
- **Cycle-timed:** ask at $2,000 on the 2nd traded day of the cycle, then $500 less each traded day after, down to $500.
- **Best-day stop $X:** no new entry once today's P&L is at least max(the cycle's P&L before today, $X), because one more
  win would make today more than 50% of the cycle.

What the results say:
- No policy beats today's (ask $1,500, no day stop) on BOTH the first payout and the $ in BOTH halves (`pick3` in the
  tool).
- The fastest H1 pick moves the first payout by 1 session at most, and costs $14-20 a month.
- Asking $2,000 is the richest in H1 (+$1 to +$3) but 1 session slower in H2.
- Why it barely matters:
  - A LIT winner usually jumps the account well past any ask line in one day.
  - The real brakes are the 2-traded-days cycle and the 50% best-day rule. Only more winning days help with those, and
    that is the ATLAS / BLITZ stack.
  - Smaller, earlier requests also use up the 5-payout limit sooner.
- **Rejected: keep ask $1,500.**

Zlarior from its hole, eval -> funded, with the calendar (from 2026-11-17):

| Route | 1st payout H1 / **H2** / 2021-25 | date (H1 / H2) | no pay 6m | $/mo |
|---|---|---|---|---|
| today: hole eval, funded LIT alone | 53 / **50** / 88 | Feb 1 / Jan 27 | 8.9 / 11.0 / 92.5 | $739 / $709 / -$5 |
| hole eval, funded + ATLAS $500 | 41 / **40** / 75 | Jan 14 / Jan 13 | 5.2 / 7.1 | $1,142 / $1,152 / -$1 |
| + fresh eval now, funded LIT alone | 46.5 / **44** / 77 | Jan 21 / Jan 19 | 7.8 / 9.2 | $777 / $754 / -$9 |
| **+ fresh eval now, funded + ATLAS $500** | **33 / 33** / 53 | **Jan 4 / Jan 4** | 5.1 / 7.2 / 90.2 | **$1,197 / $1,206** / -$2 |
| + fresh eval now, funded + ATLAS $500 + BLITZ $300 | 31 / **30** / 52 | Dec 30 / Dec 29 | 4.6 / 5.7 / 89.6 | $1,308 / $1,347 / $1 |

## 6. Honest limits

- **Stale start numbers.** The hole numbers are from 2026-11-07. The thresholds above say which side of the line
  today's numbers fall on. Re-run with the real room and to-go.
- **Same signal on two evals.** A parallel eval trades the same signal, so the two evals move together. That is why the
  gain is the fresh eval's bigger room, not two independent tries. MFFU copy trading is allowed (help center, STATE).
- **Not modelled.** The parallel eval needs the fleet copy route on the PC. If one passes while the other still holds a
  trade, that trade is not modelled.
- **ATLAS is a stand-in.** ATLAS's 25K eval here is a stand-in for the second_account_b executor (2-week pass 64% / 44% vs
  the published 57% / 35%). ATLAS's "session 20" is assumed.
- **ATLAS on three accounts.** ATLAS's own 25K, the new 25K and Zlarior's funded 50K would carry the same ATLAS signals.
  ATLAS days hit all of them at once.
- **Asia entries.** The LIT Asia slot needs entries the PC route blocks today.
- **One seed pair** (7 / 23), as stack-one-account. The grid uses 500 paths. Gaps under about 1 session or $20 a month
  are noise.
- **2021-25.** Every option pays about $0 a month there: it is a 2026 bet.
- **Nothing live changed.** No live_model*.json, second_model.json, engine file, sw.js or dashboard file was touched.
  Buying an eval is the owner's call. Any route needs the lead's build and a Sim test.
