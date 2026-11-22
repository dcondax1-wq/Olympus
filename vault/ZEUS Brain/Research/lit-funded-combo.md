---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
  - lane/combo50k
type: "research"
date: "2026-10-20"
status: "adopt-candidate"
source: "research/writeups/lit-funded-combo.md"
aliases:
  - "LIT funded accounts on the new live LIT"
---

# LIT funded accounts on the new live LIT

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT funded accounts on the new live LIT (t_check + scale-in + BE+1.25) - what to buy, in what order, and what it pays

## Summary

The funded-account studies (lit-funded-firms, lit-mffu-rapid-stack, lit-builder-25k, lit-funded-sizing, the payout habit of lit-money-batch2) were re-run on the trades of the new live LIT, with the 15-minute check, one scale-in add after breakeven and breakeven at entry + 1.25 pts all on (630 engine trades, 2026 120, 52 with an add). Every account sizes its adds with the live rule, capped by its own max contracts. Where a best-day rule applies, the adds are trimmed so the day's win stays inside the cap. The current plan (MFFU Builder 50K + LucidPro 50K + FundedNext Rapid Daily 50K, $377 up front) makes $2,147 a month over 6 months net of every fee on Jul-Oct trades (H2, the number to quote; $2,655 on Jan-Jun), from the study of 2026-11-04 05:27 with the live presets. Months 4-6 make $2,792 (Jul-Oct) and $3,292 (Jan-Jun). The 6 months lose money in 5.2% of paths (Jul-Oct). Each account loses its funded account in 6 months 0.9-1.5% of the time. Adding a Builder 25K one week later adds about $290 a month, and a second LucidPro a week later adds about $840. A Rapid EOD adds about $1,265 a month, but it needs MFFU's written OK, its eval takes about 2 months and the funded news ban costs it a third of the Jul-Oct points. On a cash budget the best order is Builder 50K, LucidPro, FundedNext, LucidPro #2, LucidPro #3, FundedNext #2, each bought when the cash (budget + payouts) allows: $3,280 a month on $300, $4,251 on $600 and $5,090 on $1,000 (H2). On 2021-25 every mix loses money (-$26 to -$144 a month). Paper only; nothing live changed.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]], [[50K combo]]
- Refers to: [[lit-funded-firms|LIT on 3 funded accounts]], [[lit-mffu-rapid-stack|LIT on stacked MFFU Rapid / Rapid EOD 50K accounts next to the Builder 50K]]
- Runs: `lit_fc_mffu_builder_50k, lit_fc_lucid_pro_50k, lit_fc_fn_rapid_daily_50k, lit_fc_fn_rapid_pro_50k, lit_fc_mffu_builder_25k, lit_fc_mffu_rapid_eod_50k, lit_fc_mffu_rapid_50k, lit_fc_stack_current, lit_fc_stack_rapid_eod, lit_fc_stack_25k_week`
- Source: `research/writeups/lit-funded-combo.md`
- Back to [[ZEUS Home]]
