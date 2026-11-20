---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-19"
status: "adopt-candidate"
source: "research/writeups/lit-funded-firms.md"
aliases:
  - "LIT on 3 funded accounts"
---

# LIT on 3 funded accounts

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT on 3 funded accounts - which 2 to add next to the MFFU Builder 50K, how to size each, and what it pays a month

## Summary

Rules were re-checked on 2026-10-19 for the firms whose rules let this bot run (bots allowed, NinjaTrader available, the same bot allowed at other firms). Each plan was played end to end on the exact live LIT trades of 2026 with an eval sizing and a funded sizing tuned to that plan's rules on Jan-Jun and checked on Jul-Oct. Recommended: keep the MFFU Builder 50K and add a LucidPro 50K and a FundedNext Rapid Daily 50K. Over 6 months from the purchase, net of every fee, the three pay on average $2,655 a month on Jan-Jun 2026 trades and $2,147 on Jul-Oct (months 4-6, once all three are funded, $3,292 / $2,792; the study of 2026-11-04 05:27 with the live presets). The accounts trade the same signals, so their results are 83-88% correlated. The 6 months lose money in 3.1% (Jan-Jun) and 5.2% (Jul-Oct) of the paths. Losing all three funded accounts is rare (0.1%), because the funded sizing shrinks with the room. On 2021-25 (reference) every plan and every combination loses money. A Tradeify account is ruled out because Tradeify bans running the same bot at another firm. Apex, Take Profit Trader, Alpha and Elite ban full automation or NinjaTrader. MFFU Rapid models the most money but is held back for now, for two reasons: MFFU has not said a Rapid can sit next to a Builder 50K, and its funded news ban could cut it to a quarter (77% of LIT's 2026 points come from trades open at 08:30 ET). Paper only.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-19]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-funded-sizing|LIT funded sizing]]
- Runs: `lit_ff_mffu_builder_50k, lit_ff_lucid_pro_50k, lit_ff_fn_rapid_daily_50k, lit_ff_mffu_rapid_50k, lit_ff_mffu_rapid_50k_news, lit_ff_mffu_rapid_eod_50k, lit_ff_mffu_rapid_eod_50k_news, lit_ff_fn_rapid_pro_50k, lit_ff_mffu_builder_25k, lit_ff_tradeify_growth_50k, lit_ff_bulenox_eod_50k, lit_ff_topstep`
- Source: `research/writeups/lit-funded-firms.md`
- Back to [[ZEUS Home]]
