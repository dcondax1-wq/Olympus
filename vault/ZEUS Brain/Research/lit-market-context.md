---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-20"
status: "rejected (no adopt-candidate)"
source: "research/writeups/lit-market-context.md"
aliases:
  - "LIT market context"
---

# LIT market context

> [!failure] Verdict: rejected
> rejected (no adopt-candidate)

**Full title:** LIT market context - dealer gamma, vanna, the VIX term structure, the options calendar and the 0DTE move as size, target or breakeven tilts

## Summary

2,520 context variants were tested on today's live LIT trades and on the adopt-candidate combo (t_check + scale_in + be_off). The context sources were dealer gamma and dark-pool buying (SqueezeMetrics GEX / DIX), vanna proxies (yesterday's VIX and SPX change), the VIX term structure and vol-of-vol (VIX9D, VIX3M, VVIX, SKEW), the 0DTE-implied move (VIX1D / VIX) and the options calendar (OPEX day and week, the week after OPEX, quad witching, VIX expiry, month-end and turn of month). Context was used only as a size tilt, a target / bank change or a breakeven change, never to skip a trade: the trade list is identical in every variant. Judged on the real eval path (two_week for 10 sessions, then safe_eval, no reset, $1.90 a micro, true 1m), pick on H1, check on H2. None passed the strict test: net $ up in both halves, no rise in 2-week fails, neighbouring thresholds holding, more than a handful of trades. 12 of 1,076 size tilts and 73 of 1,444 target / breakeven variants made more money in both halves, about what chance gives; each then failed on more fails, broken neighbours or 1-3 changed trades. The classic dealer-gamma idea (wider target on low gamma, nearer on high gamma) loses $5-17k per half. CBOE put/call is not testable (the free file stops in 2019), and there is no free historical vanna data. Nothing changes in live_model.json.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[cross-market-context|Cross-market and regime context]], [[lit-big-ideas|LIT big ideas]], [[lit-more-setups|LIT more setups a week]]
- Runs: `lit_ctx_gex_chg_dir_q0_67_0_06473_hi_x1_5, lit_ctx_spx_chg_q0_2_0_534_lo_x1_5, lit_ctx_d1_q0_5_0_7505_lo_x1_5, lit_ctx_vvix_q0_5_nobe, lit_ctx_vvix_q0_5_be2, lit_ctx_d1_q0_67_nobe, lit_ctx_all3_dix_pct_q0_8_0_481_hi_x0_75_lo_x1_25, lit_ctx_all3_tom_x1_5, lit_ctx_all3_gex_q0_5_5_345e_09_lo_x1_5, lit_`
- Source: `research/writeups/lit-market-context.md`
- Back to [[ZEUS Home]]
