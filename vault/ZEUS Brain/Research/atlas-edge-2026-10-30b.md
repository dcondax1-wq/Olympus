---
tags:
  - zeus/research
  - family/risk
  - verdict/promising
  - bot/atlas
type: "research"
date: "2026-10-30"
status: "promising - nothing passes cleanly. Round 2 - the clean version (eval unchanged, the funded 25K adds sh_asia only, market entry) passes the slot gate on 20 of 20 seeds (H1 $697 / H2 $399 / 2021-25 ..."
source: "research/writeups/atlas-edge-2026-10-30b.md"
aliases:
  - "ATLAS edge, day session"
---

# ATLAS edge, day session

> [!tip] Verdict: promising
> promising - nothing passes cleanly. Round 2 - the clean version (eval unchanged, the funded 25K adds sh_asia only, market entry) passes the slot gate on 20 of 20 seeds (H1 $697 / H2 $399 / 2021-25 $4 a month vs $574 / $374 / -$7) and is the H1-only pick of the 15 funded member sets, but its clean H2 gain is +$26 a month and $0 on the real calendar path, and account B cannot route 18:00-02:00 entries yet; BLITZ as a funded member rejected (H2 matched by its random-direction twins). One ...

**Full title:** ATLAS edge, day session (2026-10-30 b) - the stop hunts pay most on the FUNDED 25K; the NA day-hold member's extra money was eval-path money, not owner money; funded size rules are noise

## Summary

Owner 2026-10-30 - "make ATLAS way better". Two directions (the coordinator moved windows and entry execution to another agent at 13:00) - (1) make last night's paper lead (the stop hunts x0.5 + the NA day-hold member x0.5, run ab_atlas_na_hunts_lead) pass every gate, (2) funded-stage money. New tool - a whole-account SLOT simulator (eval -> funded -> MFFU payouts -> a new $63 eval; 300 block-bootstrap paths x 6 months per span) that measures $ to the owner a month net of every eval bought, next to the eval-path $ and the 25K 2-week pass / dead. Main finding - the lead's extra money was profit INSIDE evals, which is never paid; on the funded account the NA member gets 28-32% of accounts stuck in 6 months (hunts alone 3-9%), so the lead pays the owner LESS than today in H1 ($532 vs $568 a month). It can be made to pass every gate (NA only from eval session 11 / only while the room is >= $1,500, never once funded - 20 of 33 neighbours pass), but then it pays the same as the hunts alone (0 of 33 beat them). The money is in the hunts, and most of it on the funded account - eval = today's ATLAS exactly, once funded + sh_asia + sh_trend at x0.5 - slot $661 / $510 / $23 a month (H1 / H2 / 2021-25) vs today $568 / $382 / -$2; every funded weight 0.4-1.0 passes; 12 random-time twins of the hunts pass 0 times (their H2 slot averages $246); a second path set and every year 2022-25 agree. Hunts x0.5 in the eval as well + x1.0 once funded - $758 / $595 / $30 (6 of 8 neighbours). Funded rules (buffer-first, a $1,000 cap after the lock, ask lines $250-$1,500, winner caps, the 50% best-day size cap, giving up sooner, a day take-profit or day stop) move the slot by noise (+-$30) - MFFU's payout rules bind, not the size. Round 2 (coordinator) - eval = today, once funded + sh_asia only (no sh_trend) - x0.4 / 0.5 / 0.75 pass on 20 of 20 seeds (x0.5 H1 +$124, H2 +$26, 2021-25 +$11 a month; x1.0 fails H2); 12 random-time copies average H2 $306 (1 of 12 reach it); the real calendar path is flat in H2. The H1-only pick among 15 funded member subsets (frozen before any H2 number) is EMA + MACD + S/R + sh_asia - H2 rank 1 of 15, 2021-25 rank 5; dropping EMA or S/R once funded costs H2 $33-353 a month. BLITZ as a funded member (1 micro / its own size) - H1 +$186 but H2 +$19-35 is matched by random-direction BLITZ in 2 of 6 draws, 2024 worse on every seed: rejected. Paper research only.

## Money first

**Verdict: nothing passes cleanly. Keep ATLAS as it is. Drop the NA day-hold member from the plan. The real money lead is
the two stop hunts on the FUNDED 25K.**

"Slot $" = what one ATLAS 25K slot pays YOU a month over 6 months: the eval, the funded account, MFFU's payouts (80% to
you, the $1,100 buffer, $250-$1,000 a request, the 50% best-day rule, 2 traded days a cycle, 5 payouts = graduated), and a
new $63 eval after every fail, stuck account or graduation. "Eval-path $" = the profit made inside back-to-back evals
less the fees (last night's measure). **Eval profit is never paid out; slot $ is the money.**

| ATLAS 25K | H1 slot $/mo | **H2 slot $/mo** | 2021-25 slot $/mo | H1 / H2 / 2021-25 eval-path $/mo | 2-week pass / dead H1 · H2 · 2021-25 | Gate |
|---|---:|---:|---:|---|---|---|
| **Today** | $568 | **$382** | -$2 | $1,394 / $547 / -$63 | 65.5/0.8 · 43.5/0.0 · 24.6/26.2 | |
| Last night's lead (NA x0.5 + hunts x0.5) | $532 | $488 | $30 | $2,046 / $1,584 / +$159 | **62.2/5.9** · 55.1/0.0 · 31.1/29.0 | fails (H1 eval, H1 slot) |
| The lead fixed: NA only from eval session 11, no NA once funded | $671 | $610 | $30 | $1,923 / $861 / +$45 | 67.2/0.0 · 55.1/0.0 · 25.0/23.9 | passes, = hunts alone |
| **A. Eval = today; once funded + hunts x0.5** | **$661** | **$510** | **$23** | $1,394 / $547 / -$63 (same) | same as today | **passes every numeric gate** |
| A'. Eval = today; once funded + hunts x0.75 | $715 | $528 | $30 | same as today | same as today | passes |
| B. Hunts x0.5 in the eval, x1.0 once funded | $758 | $595 | $30 | $1,655 / $665 / -$4 | 67.2/0.0 · 55.1/0.0 · 25.0/23.9 | passes |
| C. Hunts x0.75 in the eval and once funded | $750 | $650 | $36 | $1,922 / $942 / +$80 | 68.1/0.0 · 59.4/0.0 · 28.2/24.2 | passes (neighbour x0.6 fails H2) |

- **A is the cleanest.** The eval does not change at all (same trades, same 2-week pass and dead), so it cannot make the
  25K eval worse. Once funded, ATLAS also trades the Asia resweep hunt and the trend inducement hunt at half size.
  - +$93 a month in H1, **+$128 in H2**, +$25 in 2021-25 (slot paths).
  - On the real 2026 days (one slot from each half's first session): $866 vs $596 a month in H1, $1,044 vs $414 in H2;
    2025 +$70 vs -$36, 2021-24 +$33 vs +$23.
- **Why it is not an adopt-candidate:**
  - The hunts' rules were picked on H1 + 2025 + 2021-24 from 28.7 million variants (`stophunt.md`). So H1 and 2021-25 are
    not clean checks for them; only 2026 H2 is.
  - Of A's H2 gain, the trend hunt alone brings +$91 a month, the Asia hunt alone +$16 (noise). The stop-hunt audit called
    the trend hunt "not real", and it needs a 30-minute limit entry that account B cannot place yet.
  - In its favour: in H2 (the clean span) 12 random-time twins of the hunts average a $246 slot (worse than today), and
    none reaches A's $510.
- **B and C make more on the slot paths, but they change the eval** (the atlas-v2 lead). Their single real H2 path is worse:
  the eval started on 2026-07-01 with the hunts never passes inside H2 (-$34 a month vs today's +$414). A keeps today's eval
  and has no such hole.
- **Funded rules do nothing worth switching.** These move the slot by about +-$30 a month or make it worse:
  - buffer-first size, and a $1,000 cap after the lock;
  - other payout ask lines and other winner caps;
  - the 50% best-day size cap;
  - giving up a funded account sooner;
  - a day take-profit or a day stop.

  MFFU's payout rules limit what comes out, not the size. Keep today's funded preset.

**Frequency and risk** (the slot on the real days, eval + funded trades together; A vs today):

| | trades / week | weeks with 2+ | PF | net $ | $ / month traded | max DD | payouts in 6 mo (slot paths) | slot paths that lose |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| H1 today / **A** | 3.79 / **5.12** | 92.6 / 96.3% | 3.03 / 3.23 | $13,828 / $16,484 | $2,267 / $2,702 | -$1,032 / -$926 | 4.45 / 5.18 | 6.7 / 5.7% |
| H2 today / **A** | 2.88 / **5.19** | 75.0 / 87.5% | 2.88 / 3.02 | $5,779 / $9,114 | $1,558 / $2,457 | -$1,175 / -$1,071 | 3.01 / 4.01 | 18.0 / 18.0% |
| 2025 today / **A** | 3.35 / 3.95 | 77.4 / 77.4% | 1.19 / 1.11 | $2,775 / $1,613 | $226 / $131 | -$3,154 / -$4,449 | 0.48 / 0.56 | 69.3 / 67.3% |
| 2021-24 today / **A** | 3.88 / 5.00 | 87.9 / 87.3% | 1.07 / 1.03 | $3,972 / $1,855 | $102 / $48 | -$9,173 / -$8,885 | 0.37 / 0.58 | 73.7 / 64.7% |

The trading $ is the money made on the accounts (most of it is never paid out); the slot $ above is what MFFU pays you.
In 2025 / 2021-24 A trades less profitably on the real path but gets more payouts and fewer losing slots: the hunts make
the funded account reach the payout line more often, while the extra trades lose a little in between.

**The 25K eval for A = today's ATLAS** (the change is funded-only): 2-week pass / fail 65.5 / 0.0 (H1), 43.5 / 0.0 (H2),
30.1 / 0.0 (2025), 22.9 / 0.0 (2021-24); dead (fail + stuck) 0.8 / 0.0 / 23.3 / 27.1; decided in 2 weeks 66.3 / 43.5 /
53.4 / 50.0; 4-week pass / fail 76.1 / 0.0, 61.0 / 0.0, 33.9 / 0.0, 26.4 / 0.0; median sessions to pass 5 / 6 / 4 / 4;
passes slower than 3 weeks 4.3 / 13.3 / 2.4 / 3.3%.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-30]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas-funded|ATLAS's funded account]], [[atlas-v2|ATLAS v2]], [[stophunt|STOP-HUNT family]]
- Runs: `atx_today, atx_funded_hunts_w05, atx_funded_hunts_w075, atx_hunts_w05_funded_w1, atx_hunts_w075, atx_lead_na_s11_funded_hunts, atx_lead_as_is, atx2_funded_asia_w05, atx2_funded_asia_w075, atx2_funded_asia_w10, atx2_funded_blitz_w05, atx2_funded_blitz_1micro`
- Source: `research/writeups/atlas-edge-2026-10-30b.md`
- Back to [[ZEUS Home]]
