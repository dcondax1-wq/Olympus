# Setup grades (A+/A/B/C) + conviction sizing: every bot (2026-11-28, research only, nothing live changed)

Owner: "the bot should risk a good amount based on each trade, what it thinks: A+ setups, B+ setups."
**Answer: NO, grading still doesn't separate.** A grade fitted on 2026 Jan-Jun ranks Jan-Jun trades well (that's in-sample)
and then flips or goes flat on Jul-Oct and 2021-25. All 18 variants fail (Holm p 1.0 for all of them). On the 50K account,
every grade map earns less in Jul-Oct than today's flat size. This is the same answer as meta-labeling (10-23), edge-d
(11-22), the calm-person grade (11-18) and the A+ score (10-30).

Design pre-registered first (DESIGN.md, e0f72071). Trades: tools/money/combo_account store (to 2026-10-16), costs in.
features.py (16 entry facts, only bars before entry) -> grades.py (results_raw.json) -> accounts.py (results_accounts.json).

## 1) Does the grade rank trades? (Spearman of score vs R; mean R by grade)
| bot / grader | Jan-Jun (fit) | Jul-Oct | 2021-25 | A+ vs C mean R, Jul-Oct |
|---|---|---|---|---|
| LIT G1 (fitted) | +0.33 (p .002) | **-0.24** | -0.05 | A+ -0.73R vs C +1.30R (flipped) |
| LIT G2 (trader's prior) | +0.17 | -0.23 | -0.09 | A+ -0.65R vs C +1.36R |
| ATLAS G1 | +0.22 (p .01) | +0.10 (p .23) | +0.18 (p .001) | A+ +0.59R vs C -0.39R |
| ATLAS G2 | -0.13 | -0.21 | -0.11 | - |
| BLITZ G1 | +0.20 (p .004) | -0.14 | -0.02 | A+ +0.12R vs C +0.35R |
| BLITZ G2 | +0.04 | -0.12 | -0.03 | - |
The one weak thread is ATLAS G1: it ranks the right way in all 3 periods. But its 2021-25 A+ bucket loses (-0.03R vs B +0.20R),
so it doesn't turn into money (below).

## 2) Money at a reference size (LIT engine size, ATLAS $500, BLITZ $300 a trade)
| bot | live H1 / H2 / 2021-25 $/mo | best map H1 / H2 / 2021-25 $/mo | trades/wk (H1/H2) | why it fails |
|---|---|---|---|---|
| LIT (PF 4.79 / 2.75 / 0.99) | $5,759 / $2,585 / -$27 | G1 M1: $7,508 / **$1,954** / -$12 | 3.1 / 2.6 | Jul-Oct -$631/mo (in-sample Jan-Jun gain only) |
| ATLAS (PF 3.05 / 2.35 / 1.13) | $7,547 / $3,256 / $739 | G1 M1: $7,700 / $3,544 / **$666** | 4.2 / 3.2 | 2021-25 -$3,751; vs equal-risk flat size only +$83 H2; shuffle p .23 |
| BLITZ (PF 1.44 / 1.76 / 1.05) | $1,133 / $1,319 / $168 | G1 M3: $1,723 / $1,383 / **-$7** | 8.6 / 7.0 | 2021-25 goes negative; it's leverage (flat x1.27 does as well) |
Max DD: every up-size map raises it (LIT H1 -$2,416 -> -$2,699..-$3,317; ATLAS 2021-25 up to -$25.7k). Full table: results_raw.json.

## 3) The account: LIT + ATLAS on the Builder 50K (combo live row, every MFFU rule, 1,000 paths)
| sizing | Jan-Jun pass / fail, days, $/mo, 1st payout | Jul-Oct pass / fail, days, $/mo, 1st payout | 2021-25 pass / fail, $/mo |
|---|---|---|---|
| **today (flat)** | 96.6 / 3.0%, 10, $2,529, s30 | 89.2 / 8.8%, 11, **$1,457**, s39 | 28.7 / 67.8%, -$2 |
| G1 M1 (1.5 / 1.25 / 1 / 0.5) | 98.2 / 1.7%, 9, $2,802, s27 | 86.3 / 10.7%, 13, $1,316, s42 | 29.0 / 66.2%, -$7 |
| G1 M2 (C skipped) | 97.4 / 2.6%, 9, $2,808, s27 | 78.9 / 16.6%, 15, $1,015, s49 | 30.0 / 62.2%, $6 |
| G1 M3 (2 / 1.5 / 1 / 0.5) | 96.4 / 3.5%, 8, $3,136, s26 | 81.5 / 17.7%, 11, $1,280, s42 | 28.7 / 68.6%, -$8 |
| G2 M1..M3 (prior) | $1,509-$2,151 | $400-$868, fail 11-24% | -$30..-$36 |
Every grade map loses money in Jul-Oct: -$141 to -$1,057 a month, with more blown evals. The Jan-Jun gains are the fit itself.

## POSEIDON (order-flow lane A)
NOT GRADABLE: there's no real tick data for Jan-Jun 2026 (ticks start Sep 2026, about 40 lane A trades), so no grade can be
fitted on H1. Its pre-registered forward gate (30 paper trades from 2026-11-27) stays the only test.

## Plain verdict
Size by grade: NO for LIT, ATLAS and BLITZ. The facts we can see at entry don't say which trade will win. A bigger size on
"A+" just bets bigger on noise, and it gets paid only in the half the grade was fitted on. Keep the flat size (live sizing
already follows the stop and the eval room). Revisit only with new information (real order flow once POSEIDON's forward
gate has 30 trades), not with new mixes of the same entry facts.
