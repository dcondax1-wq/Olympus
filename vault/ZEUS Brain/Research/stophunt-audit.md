---
tags:
  - zeus/research
  - family/other
  - verdict/finding
  - bot/atlas
type: "research"
date: "2026-10-23"
status: "finding"
source: "research/writeups/stophunt-audit.md"
aliases:
  - "STOP-HUNT audit"
---

# STOP-HUNT audit

> [!info] Verdict: finding
> finding

**Full title:** STOP-HUNT audit - trying to break the Asia resweep hunt and the trend inducement hunt

## Summary

An adversarial check of the two stop-hunt leads (stophunt.md) before anyone trusts them, 7 checks. The code is honest. An independent rewrite reproduces every trade (558/558 Asia, 467/467 trend, every field), there is no look-ahead (30/30 trades per lead re-derived on data cut at the signal), and costs hurt only a little (+1 tick plus 1 extra night tick keeps 78-99% of the money). Both leads are positive in every year 2022-2026 and in 95-98% of the one-step neighbours. The proof is weak. The leads are NOT the pick rule's own top choices: the trend hunt was number 10 of its 12-pick shortlist and had the best H2 of the 12; the Asia hunt was number 9 and had the 2nd best H2. So 2026 H2 was not really untouched. On H2 alone the Asia hunt is not significant (t 0.8, p 0.21, 3 best trades = all its H2 money). The trend hunt looks significant (p 0.03-0.05), but that drops to p 0.3-0.4 once you allow for picking the best of 12. Deflated Sharpe is about 0 for both against the size of the search. True out-of-sample test - the researcher's own search re-run on 2021-11..2024-12 only. The generic grid's picks lose in 2025 and 2026. Inside the trend family every pre-2025 shortlist pick loses in 2025 (0/12) and in H2 (0/12), and the trend lead itself would not even have been eligible (2024 PF 1.11). Inside the Asia family the pre-2025 picks stay positive in H2 (12/12) and mostly in 2025 (10/12), but they are other variants (equal highs/lows, late Asia), and the Asia lead ranks about 12,000th. Eval paths reproduce exactly, but "0 fails in 2 weeks" hides the STUCK accounts. With the hunts on the 25K, 30-42% of 2025 / 2021-24 evals are dead in 2 weeks (4-9% in 2026 H2). The Asia hunt beats a random-time placebo member by 18-22 points of 2-week passes in 2026. The trend hunt does no better than random in H1, and its flipped-direction twin passes more. Verdict - Asia resweep hunt WEAK (paper only, do not size up); trend inducement hunt NOT REAL (consistent with selection luck). Neither goes on an eval.

## Money first

- **Asia resweep hunt: WEAK, paper only.**
  - The code is right, there is no look-ahead, and it survives costs, neighbours and every year.
  - Two independent signs that the region carries something: the pre-2025 search finds positive H2 variants in the same
    family, and it beats placebo members in the eval path.
  - But the exact variant is not significant on its only clean period (H2 p 0.21; 3 trades are all of H2), it was not the
    rule's own pick, and it does not survive the multiple-testing correction.
  - It is fine to paper-log it as an ATLAS member on account B. Do not quote +$2.9k H2 as a forecast, and judge it on 40+
    fresh paper trades before any money. A fair expectation is "about flat to slightly positive".
- **Trend inducement hunt: NOT REAL as evidenced.**
  - Its best number (H2 +$4.9k, PF 2.30) is the best H2 of a 12-variant shortlist it was picked from, and its family is
    rarer than chance.
  - The same search run without 2025-26 picks 12 variants that all lose in 2025 and 2026 H2.
  - The lead itself would not have passed the pick rule before 2025.
  - In the eval path it is no better than a random member outside H2.
  - Do not route it; if it is paper-logged, treat it as a control, not a candidate.
- **Neither goes on an eval, the 50K or real money.** LIT, ATLAS, `live_model*.json` and `second_model.json` are untouched.
- **Lesson for the next search:**
  - Fix the shortlist rank-1 as the pick before H2 is computed, or keep a final period that no script can read.
  - Report "dead in 2 weeks" (fail + stuck), not "fail".
  - Run the search pre-2025 first (check 5): it costs 10 minutes and would have flagged the trend family at once.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-23]]
- Strategies: [[ATLAS]]
- Refers to: [[stophunt|STOP-HUNT family]]
- Runs: `sh_asia_resweep, sh_trend_idm5`
- Source: `research/writeups/stophunt-audit.md`
- Back to [[ZEUS Home]]
