---
title: Rule-native search - pick by "days to the first payout" and "P(no payout in 6 months)" instead of PF / net $ (Rapid EOD 50K and Builder 50K)
family: risk
date: 2026-11-17
status: mostly negative - paper only. 36 variants were scored on MFFU's own payout rules. No second target, high-win-rate scalp or daily profit lock gets the first payout sooner in both 2026 halves. One row passes the pre-set rule. That row adds the existing BLITZ (at most 3 a day, $300) to the Rapid EOD 50K, with the first payout about 8 / 5 days sooner and +$822 / +$313 a month. It is only a lead, not an adopt-candidate. Its 3-a-day cap was chosen after the "every signal" row had been seen, the 2-a-day cap fails Jul-Oct, the chance of no payout is not lower, and in 2021-25 evals fail within 2 weeks twice as often (6.0% vs 2.9%).
summary: Owner idea 2026-11-17. MFFU pays on winning days (Rapid EOD eval best day <= 30%, funded daily above $2,100; Builder funded best day <= 50%, $2,600 above start). LIT is lumpy, so every variant was scored on the owner's two numbers, using the same trades, costs ($1.90 a micro + 1 tick) and Monte Carlo paths as stack_one_account / rapid_levers. Base rows are today's plan. Rapid EOD 50K is LIT + ATLAS $500 with the 30% guard and a $1,000 cushion kept. Its first payout comes 50 / 62 days after buying (Jan-Jun / Jul-Oct), there is a 2.4% / 8.9% chance of no payout in 6 months, and it makes $6,014 / $2,824 a month. Builder 50K is a LIT eval, then LIT + ATLAS $500 once funded: 49 / 49 days, 4.7% / 7.1%, $1,202 / $1,205 a month. Tested: (A) LIT second smaller target, 50% at 1 / 2 / 3R or 33% at 2R, everywhere or only where the consistency rule bites (8 per account); (B) ATLAS half off at 1R or a fixed 1R; (C) BLITZ as a scalp layer, first signal a day with its live exit, a fixed 1R or a fixed 0.5R (win rate 63-66%), and at most 2 or 3 a day; (D) an add-on profit lock at +$300 / +$600; alone rows. Partials cut money and do not speed the payout: LIT's 8R winners are what pay. The high-win first-signal scalp is too small to move anything. BLITZ alone at $300 never passes the eval. Rapid + BLITZ max 3 a day passes the rule: 42 / 57 days, 2.6% / 9.5%, $6,836 / $3,137 a month, 2021-25 +$68 vs +$63, and BLITZ itself makes 4.5-5.9 trades a week with PF 1.48 / 1.51 / 1.03. Only 2 of the 3 Jan-Jun winners also win Jul-Oct, against 1.5 expected by a coin flip. Builder: nothing passes. ATLAS half at 1R is about 1 day faster and +$45 a month, which is inside the noise.
runs: none (research/lab/rule_native.json)
---

## For the owner (one minute)

Each row is one account for 6 months. You buy the eval, pass, wait 2 sessions, trade funded, and buy a new one if it is lost.
"Days to 1st payout" counts calendar days from buying, the middle path of 1,000, and "never" counts as never.
The trade columns (trades a week, win %, PF, max DD) use the real days in order at a fixed $ a trade: LIT $500, ATLAS $500,
BLITZ $300. "$ a month" is what the whole account pays you after the eval fees.
Each cell shows **Jan-Jun 2026** (where the idea was picked) / **Jul-Oct 2026** (the check).

| Account and plan | trades/wk | win % | PF | $ a month to you | max DD (fixed $) | **days to 1st payout** | **P(no payout in 6 months)** | 2021-25: $ a month / eval fails in 2 weeks |
|---|---|---|---|---|---|---|---|---|
| **Rapid EOD 50K, today's plan** (LIT + ATLAS $500, keep $1,000) | 7.2 / 5.5 | 56 / 52 | 3.21 / 2.33 | $6,014 / $2,824 | -$3,017 / -$2,480 | **50 / 62** | **2.4% / 8.9%** | $63 / 2.9% |
| Rapid + BLITZ $300, **at most 3 a day** (the one pass) | 13.0 / 10.0 | 55 / 53 | 2.80 / 2.16 | **$6,836 / $3,137** | -$2,770 / -$2,480 | **42 / 57** | 2.6% / 9.5% | $68 / **6.0%** |
| Rapid + BLITZ $300, at most 2 a day | 11.5 / 8.8 | 55 / 49 | 2.91 / 2.09 | $6,539 / $2,739 | -$2,951 / -$2,480 | 43 / 62 | 3.0% / 10.5% | $72 / 5.0% |
| Rapid + BLITZ every signal (reference: BLITZ alone is 8.5 a week) | 15.7 / 12.3 | 56 / 55 | 2.68 / 2.23 | $7,104 / $3,863 | -$2,950 / -$2,480 | 41 / 49 | 2.2% / 7.5% | $85 / 7.6% |
| Rapid, LIT half off at 2R in the eval (best "2nd target") | 7.2 / 5.5 | 55 / 54 | 2.84 / 2.49 | $6,171 / $2,775 | -$3,017 / -$2,060 | 48 / 63 | 2.3% / 10.2% | $67 / 3.8% |
| Rapid + high-win scalp (BLITZ first signal, fixed 0.5R, 63% wins) | 9.5 / 7.3 | 58 / 54 | 3.06 / 2.25 | $6,040 / $2,861 | -$3,475 / -$2,480 | 49 / 61 | 3.6% / 8.7% | $69 / 3.6% |
| Rapid, LIT alone | 3.1 / 2.6 | 59 / 48 | 3.63 / 2.26 | $815 / $806 | -$3,271 / -$2,228 | 143 / 126 | 34.7% / 27.1% | -$20 / 0% |
| **Builder 50K: LIT eval, + ATLAS $500 once funded** (stack candidate) | 7.2 / 5.5 | 55 / 54 | 3.12 / 2.74 | $1,202 / $1,205 | -$3,017 / -$2,480 | **49 / 49** | **4.7% / 7.1%** | -$1 / 0.6% |
| Builder, ATLAS half off at 1R (best Builder row) | 7.2 / 5.5 | 55 / 54 | 2.72 / 2.56 | $1,246 / $1,254 | -$3,225 / -$2,480 | 48 / 48 | 3.4% / 6.7% | $2 / 0.6% |
| Builder, + BLITZ $300 at most 3 a day once funded | 13.0 / 10.0 | 55 / 53 | 2.75 / 2.48 | $1,283 / $1,214 | -$3,142 / -$2,480 | 48 / 48 | 4.6% / 7.3% | -$2 / 0.6% |
| Builder, LIT alone (live today) | 3.1 / 2.6 | 59 / 50 | 3.49 / 2.71 | $779 / $753 | -$3,271 / -$2,228 | 69 / 67 | 7.7% / 9.6% | -$9 / 0.6% |

In plain words:
- **The rule-native idea is right, but the fix is not a new exit.** Taking half off early, using a fixed 1R target or
  adding a daily profit lock all give more small winning days. None of them gets the first payout sooner in both halves.
  They all cut money, because LIT's 8R winners are what fill the account. On the Builder, a second LIT target in the
  eval slows the payout by 2-4 weeks.
- **What does help is more independent trades, not smaller wins.** Adding ATLAS was the big step (Rapid 143 -> 50 days).
  Adding BLITZ (at most 3 a day, $300) on the Rapid EOD is the only row that beats today's plan in both halves: about
  **8 days sooner in Jan-Jun and 5 days sooner in Jul-Oct**, and **+$822 / +$313 a month**.
- **Why it is only a lead, not a "do it":**
  - The "3 a day" cap was chosen after the "every signal" row had been seen.
  - "2 a day" fails in Jul-Oct.
  - The chance of no payout is not lower (2.6% / 9.5% vs 2.4% / 8.9%).
  - In a 2021-25 market, evals fail within 2 weeks about twice as often (6.0% vs 2.9%).
  - BLITZ itself only breaks even in 2021-25 (PF 1.03).
- **A high-win-rate scalp on its own account does not pay.** BLITZ's first signal at $300 wins 53-66% but almost never
  reaches the $3,000 eval target in 60 sessions (0.1% pass).
- **Builder 50K: nothing to change.** The best row (ATLAS half off at 1R) is about 1 day sooner and +$45 a month. That is
  inside the Monte Carlo noise (the same plan on other random seeds moves by up to 5 sessions).

Next (paper only, nothing changed):
1. Nothing to switch now. Keep today's plan: one Rapid EOD with LIT + ATLAS $500, and the $1,000 cushion.
2. If you want the lead: BLITZ on the Rapid EOD at most 3 a day, $300 a trade. Watch it on paper (it already runs hidden)
   for 4-6 weeks before any yes / no.
3. Re-check: `python -X utf8 tools/money/rule_native.py`

## 1. What was tested and how

- **The scorer.** Days to the first payout = the median over ALL 1,000 six-month paths of the first payout session,
  counted from the day the eval is bought (a path that never pays counts as never). Days = sessions x 7/5. Also reported:
  P(no payout in 6 months), P(a payout within ~30 days = 21 sessions), $ a month after fees, and the eval (median sessions,
  2-week pass / fail).
- **The machinery is unchanged** (`tools/money/stack_one_account.py`, `tools/money/rapid_levers.py`):
  - Stored LIT (live), ATLAS (never opposite LIT) and BLITZ (never opposite LIT / ATLAS) trades.
  - LIT at its live eval size (two_week) and the fleet funded size (UP50). The added strategies risk min($ cap, 30% of the
    room, the $1,000 soft day left).
  - On the Rapid EOD: the fleet's 30% best-day size guard in the eval, the funded Tier-1 news rule (-2 / +2 min), and the
    $1,000 cushion (rapid-levers lead, now the plan).
  - Monte Carlo: eval 2,000 x 60 sessions (seed 7); slot 1,000 x 126 (seed 23); 5-session blocks; every row on the same paths.
  - The base rows reproduce the earlier studies: Rapid $6,014 / $2,824 / $63 = rapid-levers "keep $1,000"; Builder
    $1,202 / $1,205 / -$1 = stack-one-account.
- **New code (only in this file):**
  - **(A / B) Second target.** A share p of the position is taken off at k x R by limit order, with no slippage. The rest
    follows the live plan: BE + costs, the 15-minute check, the VIX-band target banked at 8R.
  - **The hit.** A bar after the entry bar must reach the level before the exit. The exit bar counts only for a winning
    trade, so a same-bar tie is a miss. Bars come from the CME NQ1! exports (1m in 2026, 5m in 2021-25). Entries come from
    the ledger for LIT and from the stored path for ATLAS; BLITZ uses its own MFE. The LIT ledger matches the bars on all
    631 trades, and all 75 "TARGET" exits show the target reached.
  - **Sizing.** It is unchanged. The Rapid 30% guard is measured on the smaller planned max win.
  - **The share p** is applied as a fraction of the position. At 1-2 micros the real split would be cruder.
  - **(C) BLITZ cap.** The first 1 / 2 / 3 BLITZ signals of a day are kept; later ones are dropped. A fixed kR target uses
    BLITZ's MFE.
  - **(D) Profit lock.** No new ATLAS / BLITZ entry once the day's closed P&L is at +$X. LIT is untouched.
- **Already in "Tested and rejected" and NOT redone as such:** partials and trails on PF (here they are re-scored on the
  payout clock), eval day caps on the Rapid (rapid-levers: the 30% guard is best), and the Builder best-day day stop
  (builder-levers). BLITZ on its own 25K (blitz-25k) and on LIT's funded 50K (scalp-na-mffu) were tested before. LIT +
  ATLAS + BLITZ on a Rapid EOD was a row in stack-one-account; the trade caps here are new.
- **Pass rule (set before the run).** A variant must beat the base in BOTH Jan-Jun and Jul-Oct:
  - The first payout median is earlier by more than the seed noise. The noise is the base re-run on seeds (8, 24) and
    (9, 25): Rapid 2 / 1 sessions, Builder 5 / 1 (Jan-Jun / Jul-Oct). If the median is equal, P(no pay) must instead be
    lower by more than its own noise.
  - P(no pay) is no worse than base + noise.
  - $ a month is at most 10% lower.
  - In 2021-25: the new layer's trades at fixed $ do not lose money, the slot $ a month is at most $25 below the base, and
    the new layer trades 2-8 times a week in every span. Here "2-8 a week" is read as the new layer's own count. The base
    (LIT + ATLAS) already makes 7.2 a week, so any add-on breaks an account-wide 2-8.
- **Added after the pre-set run:** a paired test on the same paths (mean first-payout session, with "never" = 127, ± 1
  standard error) and the BLITZ "at most 2 / 3 a day" rows. Those two rows were added after the first pass showed
  "every signal" winning on the payout clock but failing 2-8 a week.

## 2. Rapid EOD 50K (base: LIT + ATLAS $500, 30% guard, keep $1,000)

Cells show Jan-Jun / Jul-Oct / 2021-25. "Paired" = the mean first-payout session vs the base on the same paths (negative =
sooner), ± 1 standard error.

| Variant | days to 1st payout | P(no pay 6m) % | $ a month | eval median sessions | 2-wk fail % | paired sessions (H1 / H2) | rule |
|---|---|---|---|---|---|---|---|
| base | 50 / 62 / never | 2.4 / 8.9 / 85.7 | 6,014 / 2,824 / 63 | 22 / 21 / 29 | 0 / 0 / 2.9 | | |
| A LIT 50% at 1R, everywhere | 49 / 71 | 2.0 / 12.6 / 85.6 | 5,551 / 1,989 / 68 | | | -1.8 ± 0.5 / **+8.7** ± 0.7 | no |
| A LIT 50% at 1R, eval only | 48 / 66 | 2.1 / 9.7 / 85.4 | 6,186 / 2,713 / 72 | | | -2.9 / +3.0 | no |
| A LIT 50% at 2R, everywhere | 48 / 64 | 2.1 / 8.8 / 85.5 | 5,635 / 2,462 / 67 | | | -1.9 / +2.2 | no |
| A LIT 50% at 2R, eval only | 48 / 63 | 2.3 / 10.2 / 85.9 | 6,171 / 2,775 / 67 | 20.5 / 21 / 28 | 0.1 / 0 / 3.8 | -2.6 / +1.2 | no |
| A LIT 50% at 3R, everywhere | 49 / 63 | 1.9 / 6.3 / 83.9 | 5,709 / 2,787 / 78 | | | -0.9 / -0.1 | no |
| A LIT 50% at 3R, eval only | 49 / 63 | 2.5 / 9.1 / 85.3 | 6,088 / 2,790 / 72 | | | -1.2 / +0.8 | no |
| A LIT 33% at 2R, everywhere | 49 / 66 | 2.3 / 8.8 / 86.8 | 5,750 / 2,548 / 66 | | | -1.0 / +3.0 | no |
| A LIT 33% at 2R, eval only | 49 / 64 | 2.5 / 9.9 / 87.4 | 6,099 / 2,739 / 62 | | | -1.4 / +2.3 | no |
| B ATLAS half at 1R | 55 / 60 | 3.3 / 7.3 / 91.7 | 4,226 / 2,573 / 4 | | | +3.9 / -1.9 | no |
| B ATLAS fixed 1R | 87 / 71 | 13.6 / 9.3 / 93.0 | 1,893 / 1,969 / -27 | | | +27.7 / +6.8 | no |
| C BLITZ first a day, live exit | 48 / 60 | 3.0 / 8.4 / 86.1 | 6,051 / 2,945 / 62 | | | -1.5 / -1.4 | no (BLITZ loses in 2021-25) |
| C BLITZ first a day, fixed 1R | 48 / 60 | 3.3 / 8.5 / 85.9 | 6,059 / 2,932 / 69 | | | -1.0 / -1.6 | no |
| C BLITZ first a day, fixed 0.5R | 49 / 61 | 3.6 / 8.7 / 85.4 | 6,040 / 2,861 / 69 | | | -0.6 / -0.8 | no |
| C BLITZ at most 2 a day * | 43 / 62 | 3.0 / 10.5 / 84.5 | 6,539 / 2,739 / 72 | 18 / 21 / 23 | 0.1 / 0 / 5.0 | -4.9 / +1.1 | no (H2) |
| **C BLITZ at most 3 a day *** | **42 / 57** | 2.6 / 9.5 / 84.8 | **6,836 / 3,137 / 68** | 17 / 19 / 23 | 0.1 / 0 / **6.0** | **-6.2 ± 0.6 / -2.1 ± 0.7** | **PASS** |
| C BLITZ every signal (ref) | 41 / 49 | 2.2 / 7.5 / 82.8 | 7,104 / 3,863 / 85 | 17 / 17 / 22 | 0 / 0 / 7.6 | -6.8 / -8.2 | no (8.5 a week) |
| D add-on lock at +$300 | 53 / 60 | 3.4 / 7.7 / 88.0 | 5,039 / 3,038 / 37 | | | +2.8 / -2.0 | no |
| D add-on lock at +$600 | 52 / 60 | 2.9 / 8.2 / 87.9 | 5,225 / 2,985 / 37 | | | +1.7 / -1.3 | no |
| alone: BLITZ first a day, fixed 1R | never | 100 | -16 / -16 / -17 | eval pass 0.1% in 60 sessions | | | no |
| alone: ATLAS $500 | 66 / 112 | 3.2 / 25.7 / 88.8 | 3,690 / 1,030 / 45 | 27 / 31 / 32 | | +12.5 / +31.1 | no |

\* added after the pre-set run (see section 1).

BLITZ as a layer (its own trades at $300, H1 / H2 / 2021-25):

| Version | trades/wk | win % | PF | $ a month |
|---|---|---|---|---|
| first a day, live exit | 2.3 / 1.8 / 2.3 | 52 / 46 / 51 | 1.29 / 1.57 / 0.97 | 199 / 275 / -26 |
| first a day, fixed 1R | 2.3 / 1.8 / 2.3 | 53 / 46 / 53 | 1.29 / 1.47 / 1.03 | 198 / 227 / 24 |
| first a day, fixed 0.5R | 2.3 / 1.8 / 2.3 | 63 / 61 / 66 | 1.39 / 1.31 / 1.09 | 190 / 122 / 55 |
| at most 2 a day | 4.3 / 3.3 / 4.3 | 55 / 43 / 50 | 1.59 / 1.06 / 1.00 | 713 / 57 / 7 |
| at most 3 a day | 5.8 / 4.5 / 5.9 | 53 / 53 / 50 | 1.48 / 1.51 / 1.03 | 795 / 575 / 57 |
| every signal | 8.5 / 6.8 / 8.5 | 56 / 57 / 50 | 1.49 / 1.96 / 1.04 | 1,209 / 1,447 / 127 |

## 3. Builder 50K (base: LIT eval, LIT + ATLAS $500 once funded)

| Variant | days to 1st payout | P(no pay 6m) % | $ a month | paired sessions (H1 / H2) | rule |
|---|---|---|---|---|---|
| base | 49 / 49 / never | 4.7 / 7.1 / 89.7 | 1,202 / 1,205 / -1 | | |
| LIT alone (live) | 69 / 67 | 7.7 / 9.6 / 90.6 | 779 / 753 / -9 | +13.0 / +11.2 | no |
| A LIT 50% at 1R, everywhere | 78 / 92 | 6.8 / 15.5 | 944 / 776 / -10 | +19.0 / +26.3 | no |
| A LIT 50% at 1R, funded only | 50 / 57 | 3.5 / 8.4 | 1,182 / 1,028 / 2 | +0.4 / +4.9 | no |
| A LIT 50% at 2R, everywhere | 71 / 69 | 6.7 / 9.5 | 1,012 / 989 / -6 | +14.2 / +12.2 | no |
| A LIT 50% at 2R, funded only | 49 / 53 | 4.0 / 6.9 | 1,201 / 1,126 / 0 | 0.0 / +2.2 | no |
| A LIT 50% at 3R, everywhere | 66 / 58 | 6.7 / 5.6 | 1,059 / 1,110 / 3 | +11.0 / +5.1 | no |
| A LIT 50% at 3R, funded only | 49 / 50 | 4.3 / 5.0 / 88.3 | 1,201 / 1,185 / 3 | +0.1 / -0.1 | no |
| A LIT 33% at 2R, everywhere | 64 / 60 | 5.0 / 7.2 | 1,080 / 1,071 / -5 | +8.8 / +7.6 | no |
| A LIT 33% at 2R, funded only | 49 / 51 | 4.2 / 6.3 | 1,199 / 1,157 / -1 | -0.1 / +0.8 | no |
| B ATLAS half at 1R | 48 / 48 | 3.4 / 6.7 / 88.1 | 1,246 / 1,254 / 2 | -1.1 ± 0.4 / -0.8 ± 0.4 | no (inside the noise) |
| B ATLAS fixed 1R | 57 / 55 | 9.6 / 8.7 | 965 / 1,062 / -5 | +8.5 / +4.3 | no |
| C BLITZ first a day, live / 1R / 0.5R | 49 / 48-49 | 4.9-5.8 / 7.2-7.6 | 1,204-1,216 / 1,199-1,212 | ~0 / ~0 | no |
| C BLITZ at most 2 a day * | 48 / 49 | 4.6 / 8.4 | 1,269 / 1,158 / -2 | -0.7 / +1.3 | no |
| C BLITZ at most 3 a day * | 48 / 48 | 4.6 / 7.3 | 1,283 / 1,214 / -2 | -1.2 / -0.4 | no |
| C BLITZ every signal (ref) | 46 / 45 | 4.2 / 5.7 | 1,313 / 1,347 / 2 | -2.3 / -2.9 | no (8.5 a week) |
| D add-on lock at +$300 / +$600 | 50 / 48, 49 / 48 | 5.3 / 6.2, 5.0 / 6.6 | 1,158-1,165 / 1,245-1,254 | +1 / -1.5 | no |
| alone: BLITZ first a day, fixed 1R | never | 100 | -15 | | no |
| alone: ATLAS $500 | 55 / 83 | 4.2 / 13.9 | 1,034 / 659 / 1 | +2.7 / +21.4 | no |

## 4. Chance and honesty

- **The count.** 36 variants in all, 18 per account; the 2 "alone" rows a side are references, not candidates.
  - Rapid: 3 win Jan-Jun on the pre-set rule (BLITZ at most 2 / 3 a day, every signal) and 2 of those also win Jul-Oct. A
    coin flip would give 1.5.
  - Builder: 0 win Jan-Jun.
  - **The pass is not more than chance by the count alone.** What supports it: the paired test is 3-10 standard errors in
    both halves, and BLITZ's direction edge was checked before (random directions lose: scalp-na-mffu.md).
  - What weakens it:
    - The cap was chosen after the first look.
    - At most 2 a day fails Jul-Oct: BLITZ's 2nd-signal trades made PF 1.06 there, but its 3rd made the H2 money back.
      That is noisy, not a smooth "more is better".
    - It does not lower P(no payout).
    - In 2021-25, 2-week eval fails go from 2.9% to 6.0%.
- **Why a second target does not help.** On the Rapid eval the 30% rule needs a $3,000+ profit with no day above 30%. A
  half-off plan does let the 30% guard size bigger (the planned max win is smaller), but each winner banks less, so the
  account needs as many winning days as before. Only more independent winners shorten the clock. On the Builder the eval
  has no consistency rule and LIT's big days pass it in a median of 9 sessions. Any LIT partial in the eval slows it.
- **Simplifications:**
  - A partial is a fraction of the position, which ignores 1-micro rounding.
  - A same-bar target and stop counts as a miss.
  - BLITZ's fixed target uses its MFE up to the real exit.
  - Overlapping trades of a day are played in entry order on closed P&L, as in stack-one-account.
- **Futures data only:** CME NQ1! 1m / 5m exports in `data/`. No pip installs were needed.
- **Nothing live changed:** no live_model*.json, engine, sw.js, dashboard or apps file. BLITZ on a Rapid account would need
  the owner's yes, a route built by the lead (account C rules on the Rapid) and a Sim test.
