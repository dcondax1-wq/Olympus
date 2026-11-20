---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
type: "research"
date: "2026-10-17"
status: "finding"
source: "research/writeups/risk-sizing.md"
aliases:
  - "Risk and sizing"
---

# Risk and sizing

> [!info] Verdict: finding
> finding

**Full title:** Risk and sizing: every sizing idea tested on both periods

## Summary

Changing how much the bot risks per trade moves money and drawdown together and does not fix 2021-25. More risk ($1,000-1,200, or no wide-stop scaling) makes more in 2026 but doubles eval fails; less risk drops below 2 setups a week. The changes that help both periods size down specific losing trades: quarter size in cold streaks, half size on late entries.

## Money first

- **Changing the overall risk** (a different $ amount, or different wide-stop scaling) only trades money for drawdown and eval fails.
- **The improvements that hold in both periods size down specific trades that lose in both:**
  - quarter size in cold streaks
  - half size on late entries
- They are combined in the recommendation (risk-summary.md, run `risk_pkg_q25_late_live`):
  - 2026: +$20.6k, PF 4.12, max DD -$2.2k
  - 2021-25: +$11.5k, PF 1.19, max DD -$9.2k
  - 1-month eval fails in 2021-25: 5.1%, against 9.4%
  - every setup is still traded

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-17]]
- Refers to: [[eval-sizing|Eval sizing]], [[risk-summary|Risk summary]]
- Runs: `baseline, risk_usd400, risk_usd600, risk_usd700, risk_usd900, risk_usd1000, risk_usd1200, risk_ref15, risk_ref25, risk_ref30, risk_ref40, risk_refoff, risk_shape05, risk_shape15, risk_floor400, risk_cold_lb10, risk_cold_lb12, risk_cold_lb20, risk_cold_lb25, risk_cold_thrm2, risk_cold_thrp2, risk_col`
- Source: `research/writeups/risk-sizing.md`
- Back to [[ZEUS Home]]
