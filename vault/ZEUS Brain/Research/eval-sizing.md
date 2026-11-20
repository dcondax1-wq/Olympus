---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
type: "research"
date: "2026-10-17"
status: "rejected"
source: "research/writeups/eval-sizing.md"
aliases:
  - "Eval sizing"
---

# Eval sizing

> [!failure] Verdict: rejected
> rejected

**Full title:** Eval sizing: can the eval's own state pass more MFFU evals?

## Summary

Sizing from the eval's state (cushion above the trailing max loss, profit, distance to the target) cuts eval fails a lot (2021-25 1-month fails 9.4% to 0.3-2%), but it also passes fewer evals a year and leaves 43-60% of evals stuck after 3 months, and the result depends on the exact threshold. None beats fixed sizing robustly; the recommended cold-streak / late-entry sizing improves evals more (2.63 evals bought per pass in 2021-25 vs 3.89). For the owner's 2-week rule see the fast mode in risk-summary.md.

## Money first

- **Rejected for now.** No eval-state rule beats fixed sizing in both periods once passes, fails and time are all counted.
- **Speed instead of safety:** for the owner's new rule (an eval decided within 2 weeks), the useful lever is the opposite one: drop the wide-stop scaling while the eval is healthy. See "Faster evals" in risk-summary.md (run `risk_fast_press1000`).
- **Not ruled out later.** If MFFU evals have no time limit and no monthly fee, "size down once the cushion is under $1,000" is worth a second look. It turns many fails into slow evals that are still alive. It only needs the account balance and the best end-of-day balance, so it would fit the Pine script.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-17]]
- Refers to: [[risk-summary|Risk summary]]
- Runs: `baseline, risk_eval_cap50, risk_eval_cap100, risk_eval_prop1000, risk_eval_prop1500, risk_eval_prop1000_qty, risk_eval_bank, risk_eval_presslock, risk_eval_pressup, risk_eval_defend, risk_eval_prop1000_usd1000, risk_eval_prop1000_usd1200, risk_pkg_q25_prop1000, risk_usd600, risk_usd1000, risk_pkg_q2`
- Source: `research/writeups/eval-sizing.md`
- Back to [[ZEUS Home]]
