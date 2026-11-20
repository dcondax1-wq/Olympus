---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/atlas
  - bot/blitz
type: "research"
date: "2026-10-30"
status: "rejected (both bots, no change) - the fitted scores (ridge score, points checklist; x0.5 / x1 / x1.5 or skip the worst third) are inside their shuffled-label controls and lose in 2021-25; two thin ..."
source: "research/writeups/discretion-score-2026-10-30.md"
aliases:
  - "Discretion score for ATLAS and BLITZ"
---

# Discretion score for ATLAS and BLITZ

> [!failure] Verdict: rejected
> rejected (both bots, no change) - the fitted scores (ridge score, points checklist; x0.5 / x1 / x1.5 or skip the worst third) are inside their shuffled-label controls and lose in 2021-25; two thin paper leads, not switches - a BLITZ trader's checklist (no fit, but written after the fact table was seen) and an ATLAS score fit on 2021-24 (fails the 2-week eval test)

**Full title:** Discretion score for ATLAS and BLITZ (2026-10-30) - judging each trade before entry and sizing the good ones up is at chance for both bots

## Summary

Owner 2026-10-30 - "give ATLAS and BLITZ good discretion like a skilled human trader - judge each trade before entry, trade the good ones bigger, the bad ones smaller or not at all". A combined pre-trade quality score (6 facts known at entry each - break strength, the day's range so far, VIX, the day's signal count, room to the next untaken liquidity pool, 15m market structure for BLITZ; stop size in ATR, VIX, daily ATR percentile, room to the next pool, 15m structure, the day's earlier result for ATLAS) was fit on 2026 H1 only, frozen, and used as a size rule on 2026 H2 and 2021-25 untouched, against 200 (BLITZ) / 40 (ATLAS) fits on shuffled outcomes. Neither bot's score beats its shuffled controls out of sample, and both lose per unit of risk in 2021-25. BLITZ - H2 R per $ risked +0.246 vs +0.200 (shuffled p 0.14), 2021-25 +0.009 vs +0.013 (p 0.79), 25K slot $273 / $52 / -$37 a month vs $277 / $30 / -$41. ATLAS - H2 +0.603 vs +0.620 (p 0.55), 2-week pass 62.2 / 39.1 vs 65.5 / 43.5, eval paths $1,747 / $455 a month vs $1,394 / $547. Nothing changes.

## Money first

**No change for either bot. A "discretion score" that judges each trade before entry does not make money it can keep.**

- **What was tested.** The owner asked for "good discretion like a skilled human trader": before each trade, judge its
  quality from what is known at entry, then trade the good ones bigger and the bad ones smaller or not at all.
  - One score per bot, built from 6 facts a trader would look at.
  - Fit on 2026 H1 trades only, then frozen.
  - Used as a size rule on 2026 H2 and 2021-25, which the fit never saw.
  - Two size rules: the worst third of scores x0.5, the middle x1, the best third x1.5 ("thirds"); or skip the worst third.
- **BLITZ: at chance.** The score looks a little better in 2026 H2, but random scores (fit on shuffled results) do as well
  14-41% of the time. In 2021-25 it is worse than today in every form.
- **ATLAS: at chance.** Every form passes fewer evals in 2 weeks in both 2026 halves.
  - In H2 the ridge score makes less per unit of risk than today (+0.603 vs +0.620).
  - The checklist makes more in H2 (+0.698), but random scores do as well 33% of the time, and in 2025 its eval paths lose
    more (-$276 vs -$148 a month).
- **Why.** The facts that look good in one period look bad in another. BLITZ's 5-year history likes the opposite sign on 5
  of the 6 facts, compared with 2026 H1. A score built from them is noise with a story.
- **Two thin leads for paper only, not switches:**
  - A BLITZ trader's checklist (no fitting at all) is a little better per unit of risk in every span. But random sizes
    reach it 10-12% of the time, it passes fewer 2-week evals in H2, and it was written after the fact table was seen.
  - An ATLAS score fit on 2021-24 (875 trades) is better per unit of risk in 2026 H1, H2 and 2025. But 100 shuffled fits
    reach it 6% / 19% / 43% of the time, and it fails the 2-week eval test: dead evals in H1 rise from 0.8% to 4.2%, and
    the H2 pass rate drops from 43.5% to 39.1%.

**BLITZ** (account C on its own 25K, today's rule; costs in, $1.90 a micro + 1 tick; "$500 view" = each trade risks $500 x
its size; 25K eval = 40% of the room, the full room from session 5, <= $600, x the size; slot = the whole 25K account over 6
months net of every $63 eval, 300 simulated lives; p = share of 200 shuffled-outcome fits that do at least as well per unit of
risk):

| BLITZ | trades / wk | 2+ a week | PF | net | $ / month | max DD | R per $ risked | 25K 2-week pass / fail | 25K slot $ / month | shuffled p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2026 H1, today** | 8.5 | 89% | 1.61 | +$17,849 | $2,928 | -$3,968 | +0.165 | 36.1 / 37.8 | $277 | |
| H1, score thirds (ridge) | 8.5 | 89% | 1.69 | +$19,601 | $3,216 | -$2,898 | +0.180 | 37.0 / 26.1 | $273 | 0.21 (in-sample) |
| H1, score thirds (checklist) | 8.5 | 89% | 1.68 | +$22,820 | $3,744 | -$3,860 | +0.178 | 32.8 / 36.1 | $261 | 0.40 (in-sample) |
| H1, skip worst third (ridge) | 5.7 | 85% | 1.80 | +$14,596 | $2,395 | -$2,228 | +0.201 | 31.9 / 23.5 | $241 | 0.16 (in-sample) |
| **2026 H2, today** | 6.8 | 75% | 1.82 | +$10,589 | $2,851 | -$2,968 | +0.200 | 36.2 / 34.8 | $30 | |
| H2, score thirds (ridge) | 6.8 | 75% | 2.09 | +$12,934 | $3,482 | -$2,196 | +0.246 | 30.4 / 27.5 | $52 | 0.14 |
| H2, score thirds (checklist) | 6.8 | 75% | 2.03 | +$15,670 | $4,219 | -$4,076 | +0.234 | 33.3 / 29.0 | $73 | 0.20 |
| H2, skip worst third (ridge) | 4.4 | 50% | 1.98 | +$7,724 | $2,080 | -$1,846 | +0.224 | 24.6 / 21.7 | $7 | 0.41 |
| **2021-25, today** | 8.6 | 80% | 1.04 | +$11,919 | $232 | -$21,923 | +0.013 | 20.4 / 50.2 | -$41 | |
| 2021-25, score thirds (ridge) | 8.6 | 80% | 1.03 | +$9,012 | $176 | -$24,381 | +0.009 | 23.8 / 47.4 | -$37 | 0.79 |
| 2021-25, score thirds (checklist) | 8.6 | 80% | 1.01 | +$3,945 | $77 | -$31,008 | +0.004 | 23.8 / 52.6 | -$40 | 1.00 |
| 2021-25, skip worst third (ridge) | 6.2 | 78% | 1.01 | +$1,533 | $30 | -$24,105 | +0.002 | 18.2 / 39.4 | -$46 | 0.87 |

The checklist's own skip rule is no better: R per $ risked +0.180 / +0.245 / +0.006, shuffled p 0.40 / 0.20 / 0.84 (run
`dsx_blitz_check_skip`). The 25K slot $ also sits inside its shuffled controls: ridge thirds p 0.22 / 0.29 / 0.31.

**ATLAS** (account B on its Builder 25K, the account-B need size x the score's size; eval paths = back-to-back 25K evals started
every 5th session, $ less the $63 fees, a month; "dead" = failed or stuck; p = share of 40 shuffled-outcome fits that do at
least as well per unit of risk):

| ATLAS | trades / wk (eval path) | PF ($500) | net ($500) | $ / month ($500) | max DD ($500) | R per $ risked | 25K 2-week pass / dead | eval paths $ / month | shuffled p |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **2026 H1, today** | 2.1 | 3.01 | +$49,481 | $8,112 | -$3,000 | +0.884 | 65.5 / 0.8 | $1,394 | |
| H1, score thirds (ridge) | 2.0 | 3.57 | +$61,281 | $10,046 | -$2,500 | +1.089 | 62.2 / 0.0 | $1,747 | 0.05 (in-sample) |
| H1, score thirds (checklist) | 3.4 | 3.46 | +$58,624 | $9,611 | -$2,500 | +1.020 | 63.0 / 0.8 | $1,652 | 0.05 (in-sample) |
| H1, skip worst third (ridge) | 2.4 | 3.72 | +$42,426 | $6,955 | -$2,549 | +1.131 | 55.5 / 0.0 | $1,612 | 0.15 (in-sample) |
| **2026 H2, today** | 1.6 | 2.73 | +$15,803 | $4,260 | -$2,347 | +0.620 | 43.5 / 0.0 | $547 | |
| H2, score thirds (ridge) | 1.8 | 2.57 | +$14,611 | $3,938 | -$2,296 | +0.603 | 39.1 / 0.0 | $455 | 0.55 |
| H2, score thirds (checklist) | 1.5 | 2.86 | +$16,219 | $4,372 | -$1,963 | +0.698 | 39.1 / 0.0 | $760 | 0.33 |
| H2, skip worst third (ridge) | 1.9 | 2.07 | +$7,432 | $2,003 | -$1,954 | +0.450 | 27.5 / 0.0 | $130 | 0.78 |
| **2025, today** | 2.6 | 1.15 | +$10,533 | $857 | -$9,942 | +0.084 | 30.1 / 23.3 | -$148 | |
| 2025, score thirds (ridge) | 3.0 | 1.22 | +$14,075 | $1,145 | -$9,956 | +0.127 | 19.3 / 24.5 | $38 | 0.35 |
| 2025, score thirds (checklist) | 2.3 | 1.18 | +$12,412 | $1,010 | -$10,522 | +0.105 | 20.5 / 21.7 | -$276 | 0.58 |
| **2021-24, today** | 3.1 | 1.08 | +$19,753 | $510 | -$23,036 | 

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-30]]
- Strategies: [[ATLAS]], [[BLITZ (paper)]]
- Refers to: [[atlas-blitz-edge-2026-10-30|ATLAS + BLITZ edge night]]
- Runs: `dsx_blitz_ridge_t3, dsx_blitz_ridge_skip, dsx_blitz_check_t3, dsx_blitz_check_skip, dsx_blitz_prior, dsx_atlas_ridge_t3, dsx_atlas_ridge_skip, dsx_atlas_check_t3, dsx_atlas_check_skip, dsx_atlas_prior`
- Source: `research/writeups/discretion-score-2026-10-30.md`
- Back to [[ZEUS Home]]
