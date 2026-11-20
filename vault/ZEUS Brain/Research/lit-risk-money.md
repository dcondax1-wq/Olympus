---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-20"
status: "two adopt-candidates (an eval weekly loss stop at -$1,200, and buying a 2nd eval one week after the 1st); every other idea rejected"
source: "research/writeups/lit-risk-money.md"
aliases:
  - "LIT risk and money"
---

# LIT risk and money

> [!success] Verdict: adopt-candidate
> two adopt-candidates (an eval weekly loss stop at -$1,200, and buying a 2nd eval one week after the 1st); every other idea rejected

**Full title:** LIT risk and money - equity-curve sizing, eval-game refinements, weekly stops, funded risk, and how many evals to run

## Summary

About 300 eval variants (plus 46 funded and 40 portfolio runs) on the exact live LIT trades of 2026, on the real eval path (two_week config C for 10 sessions, then safe_eval, no reset, $1.90 a micro, true 1m), each scored on live LIT and on top of the adopt-candidate combo (t_check + scale_in + be_off), picked on Jan-Jun and checked on Jul-Oct. (1) The old engine's cold-streak filter does not work on LIT - every cold, hot, drawdown and streak rule costs money or raises eval fails in one half. (2) Eval refinements (room share by session, clock press, protect near target, size after a first loss, need buffer, $-to-go caps) change nothing or hurt; after session 10 a 40% safe_eval nudges the eventual pass up but slows it (promising only); start-day rules (weekday, after a LIT loss / win / quiet days, after a cold LIT stretch) do not hold - the cold-stretch rule looks huge in 2026 but rests on 2-4 episodes and reverses in 2021-25. (3) Weekly profit stops cost money; R-based loss stops cut trades below 2 a week or lose passes. One rule holds: once an eval's week is at -$1,200 or worse, no new trade until Monday. 2-week fails 9.2 -> 5.0% (Jan-Jun) with passes unchanged, Jul-Oct pass 50.7 -> 52.2%; neighbours -$700 to -$1,500 all cut fails; 2021-25 fails 5.6 -> 5.2%. It is money-neutral (-$2 / -$3 a month in the portfolio). (4) Funded: LIT's full Kelly is 20-29% of the room; the live funded size already risks about that (max $342-412 a trade), so a ramp after payouts, Kelly fractions, room tiers or streak multipliers add nothing in both halves. (5) MFFU allows 1 sim-funded Builder 50K: buying a 2nd eval 5 sessions after the 1st (while no funded account) pays $662 / $653 a month instead of $641 / $608 and cuts the 6-month no-money risk 9.4 -> 7.4% / 14.8 -> 9.8%. Two evals the same day are the same eval twice. Paper only; nothing live changed (one default-off option added to engine/sizing.py).

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-funded-firms|LIT on 3 funded accounts]], [[lit-two-week-eval|LIT two-week eval]]
- Runs: `lit_risk_m_wk1200, lit_risk_m_wk1200_all3, lit_risk_m_wk800, lit_risk_m_portfolio_stagger5, lit_risk_m_after10_safe40, lit_risk_m_cold5, lit_risk_m_hot10, lit_risk_m_wkprofit3, lit_risk_m_funded_ramp400, lit_risk_m_funded_ref`
- Source: `research/writeups/lit-risk-money.md`
- Back to [[ZEUS Home]]
