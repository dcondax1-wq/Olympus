# All strategies on our 4 accounts: how fast is the FIRST payout? (2026-11-27, research only)

Owner: "if all strategies ran on our accounts we'd be good" / "I don't think it takes a month and a half to get payouts".
Design committed before any scored run: `DESIGN.md` (c7386902). Code `allstrats.py`, numbers `results.json`
(+1 tick BLITZ check `results_blitz_tick.json`). Engine = research/plans/rank.py + onebook (real fills, every MFFU rule),
start = today's real balances (board Nov 27), first session Mon Nov 30, 1,000 paths x 6 months a market, the same paths for
every mix, one shared risk manager per account (one position at a time, ATLAS never opposite LIT, one shared daily loss and room,
news flat on Rapid funded, 30% best day on the Rapid eval, 50% best day + 5 payouts on Builder funded). Nothing live changed.

## Short answer
- **The owner is half right.** The funded ATLAS 25K can pay in **December** (median Dec 29 in a Jan-Jun-like market, Jan 29 in a
  Jul-Oct-like one). The 3 evals have to pass first, and then MFFU's payout rules apply (the buffer plus the $1,000 request, and the 50%
  best-day rule), so their first payout is **late Jan to mid-Mar**, not December.
- **Adding bots does make payouts come sooner** (more trades, so the target and buffer fill faster): 1-4 weeks sooner on every account.
  The price is **more lost funded accounts**, and on the evals that are already low on room, **more failed evals**.
- **In a 2021-25 or 2025 market, every mix on every account loses money and almost nothing pays by Jan 31 (0-19%).** More bots don't
  fix a bad market: ATLAS at real fills has PF 0.82-0.90 there.
- **POSEIDON (order flow) can't be tested:** there are only 51 days of real ticks, with none in 2026 H1 or 2021-25. It stays forward paper.
- **Gap:** the stored trades end on Oct 16. The Oct 17-Nov 26 slow stretch (LIT 7 trades, -$858) is NOT in the 2026 markets; the
  2025 market (with April's slow stretch) stands in for it.

## Per account: today vs the best mix (median first payout date | % paid by Dec 31 / Jan 31 | eval fail % | $/month after fees)
| account | mix | 2026 Jan-Jun-like | 2026 Jul-Oct-like | 2021-25 | 2025 |
|---|---|---|---|---|---|
| Zlarior 50K eval ($1,313 room) | TODAY LIT + ATLAS x0.5 | Jan 27, 18/53%, fail 15%, $1,170 | Feb 12, 10/40%, fail 26%, $943 | none, 0/1%, fail 85%, -$43 | none, 0/1%, fail 81%, -$30 |
| | + BLITZ $150 (M09) | Jan 19, 26/66%, fail 19%, $1,372 | Jan 28, 16/52%, fail 20%, $1,169 | none, 0/2%, fail 87%, -$58 | none, 0/2%, fail 79%, -$20 |
| Zlarior 25K #2 eval | TODAY LIT | Feb 12, 11/38%, fail 2%, $365 | Feb 23, 10/34%, fail 2%, $322 | none, 0/1%, fail 30%, -$7 | none, 0/1%, fail 15%, -$1 |
| | LIT eval, all 3 once funded (M10) | Jan 26, 24/53%, fail 2%, $543 | Feb 2, 17/48%, fail 2%, $459 | none, 1/2%, fail 30%, -$10 | none, 0/1%, fail 15%, -$5 |
| Rapid EOD 25K eval | TODAY LIT + ATLAS | Feb 17, 4/31%, fail 0.1%, $1,561 | Mar 8, 3/24%, fail 1.7%, $628 | none, 0/1%, fail 73%, -$35 | none, 0/1%, fail 53%, -$18 |
| | + BLITZ $300 (M06, rule pick) | Feb 1, 15/49%, fail 1.9%, $2,181 | Feb 16, 12/39%, fail 2.1%, $1,121 | none, 2/3%, fail 72%, -$37 | none, 1/2%, fail 63%, -$11 |
| | + BLITZ $150 (M05) | Feb 8, 7/40%, fail 1.3%, $1,674 | Feb 17, 7/34%, fail 2.7%, $895 | none, 1/2%, fail 73%, -$34 | none, 1/2%, fail 58%, -$9 |
| ATLAS 25K funded ($401) | TODAY ATLAS | Dec 29, 55/74%, lost 10%, $498 | Jan 29, 28/51%, lost 14%, $277 | none, 7/9%, lost 90%, -$17 | none, 9/11%, lost 87%, -$7 |
| | + BLITZ $150 (M08) | Dec 28, 58/75%, lost 8%, $515 | Jan 8, 43/66%, lost 7%, $406 | none, 8/10%, lost 89%, -$17 | none, 11/14%, lost 85%, $0 |
| | + LIT (M03 = card alloc-lit-funded25) | Dec 18, 68/86%, lost 16%, $694 | Dec 28, 59/79%, lost 19%, $555 | none, 9/12%, lost 89%, -$25 | none, 11/14%, lost 86%, -$13 |
"fail" on ATLAS = the funded account lost before its first payout. The "first payout" counts a re-bought account's payout too.
Lost funded accounts within 6 months rise with every bot added (Rapid 24 -> 36% / 50 -> 57%, 25K #2 14 -> 28% / 17 -> 24%).
Fixed-size view (trades/week, PF, max DD) for all 39 rows is in results.json; e.g. LIT + ATLAS + BLITZ = 14.6 / 11.9 trades a
week, PF 2.33 / 1.95, 2021-25 PF 0.90.

## Pre-registered verdict (pick = best H1 % paid by Jan 31 among mixes with H1 fail <= today + 3 pts; card only if both 2026 halves are better, $ not lower, H2 fail <= +3, 2021-25 not much worse, margin >= 2 pts)
| account | rule pick | card? | why |
|---|---|---|---|
| Zlarior 50K | today (only eligible mix) | no | every other mix raises the H1 fail rate > 3 pts (M09 19.4% vs 15.0%). Near miss: M09 is better on everything else |
| Zlarior 25K #2 | M06 + BLITZ $300 | no | H2 fail 2 -> 12%, 2021-25 fail +51 pts. **Post-hoc:** M10 (LIT eval, all 3 once funded) passes every check, but the rule didn't pick it |
| Rapid EOD 25K | **M06 + BLITZ $300** | **YES** | Jan 31 paid 31 -> 49% / 24 -> 39%, $/mo +$620 / +$493, fail +1.8 / +0.4 pts, 2021-25 -$2/mo. Holds at +1 tick on BLITZ (47 / 38%, fail 2.9 / 2.4%) |
| ATLAS funded | M01 LIT alone | no | $ lower in H1. Near miss: + BLITZ $150 = H2 51 -> 66% and fewer lost accounts, but H1 only +1.4 pts (noise) |
39 rows scored (10 mixes x 3 evals + 9 on the funded account; TODAY = one of them). With ~10 tries per account, a one-account
win of a few points is weak evidence.

Honest conflicts:
- A $300 BLITZ lane on this same Rapid eval was rejected on 2026-11-24 (four-pillars) under a STRICTER +1-point fail bar
  (0.5 -> 3.1%). Here the bar was +3 points and the engine starts from today's balance. The owner keeps BLITZ on PAPER
  ("it can be paper till we study more"), and BLITZ v2 (2026-11-26) advised retiring it as a pillar.
- More bots = more funded accounts lost. The extra $ already counts the re-buys, but the owner sees more dead accounts.

## Owner yes/no cards (paper only for Claude; going live is the owner's call)
1. **Rapid EOD 25K: let BLITZ trade there next to LIT + ATLAS, one position at a time ($300 lane, or $150 to play safe).**
   Paid by Jan 31: 31 -> 49% (Jan-Jun-like), 24 -> 39% (Jul-Oct-like); about +$500-620 a month. Eval fail 0.1 -> 1.9%,
   lost funded 24 -> 36%. 2021-25: same loss as today. Passed the pre-set rule. BLITZ goes from paper to live on 1 account.
2. **Zlarior 25K #2: keep the eval LIT-only; once funded, run LIT + ATLAS + BLITZ $150.** No change until it passes. First
   payout ~2.5 weeks sooner (Feb 12 -> Jan 26 / Feb 23 -> Feb 2), +$140-180 a month, lost funded 14 -> 28%. Post-hoc lead
   (passes every check, not the rule's pick): say LATER if you want more proof.
3. **ATLAS funded 25K: add BLITZ $150 next to ATLAS.** Jul-Oct-like: paid by Jan 31 51 -> 66% and fewer lost accounts (14 -> 7%);
   Jan-Jun-like: the same (+1.4 pts). Near miss on the pre-set rule (H1 margin < 2 pts) = lead, not a proven win.
