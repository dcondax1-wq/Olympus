---
tags:
  - zeus/research
  - family/management
  - verdict/adopt-candidate
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-10-29"
status: "no adopt-candidate; one promising lead (LIT 15m structure trail, thin: 7 trades in 2026)"
source: "research/writeups/structure-management.md"
aliases:
  - "Trade like a person"
---

# Trade like a person

> [!success] Verdict: adopt-candidate
> no adopt-candidate; one promising lead (LIT 15m structure trail, thin: 7 trades in 2026)

**Full title:** Trade like a person - market structure targets, trails, CHoCH exits and higher-timeframe agreement for LIT and ATLAS

## Summary

Owner (2026-10-28) - "Written rules the bot knows, trade like a person, not a fixed rr, learn market structure." A new market-structure engine (swings, BOS, CHoCH, protected swing, liquidity pools, premium / discount on 5m / 15m / 1h) was used to test 101 LIT and 24 ATLAS management ideas on the real trades. "Not a fixed RR" (let the winner run past the target on the 15m structure) makes H1 +$13.6k / H2 +$956 at the LIT size, but two trend days are the whole gain and the eval path loses (2-week pass 57% -> 36% H1): rejected. Nothing beats the live rules in both halves of 2026 on both sizings, so nothing changes. The owner's idea "breakeven after a strong reversal" (BE on a 5m CHoCH against after +0.75R) costs H1 -$1,442 / H2 -$775. Targets at the next liquidity pool cost H1 -$6.6k to -$17.4k. Skipping trades against the 1h trend would have saved the -$437 trade of 2026-10-28 but costs H1 -$15.0k / H2 -$7.5k and halves the trade rate. The one lead: after a 15m break in the trade's favour (+1R) move the stop to the 15m protected swing: H1 +$467, H2 +$13 (LIT size), eval path H1 +$1,019 / H2 +$3,762, but one more 2-week fail in H1 (1.7% to 2.5%) and only 7 trades changed: watch it in the advisor, don't switch it on. ATLAS: the stop at the 15m protected swing passes the 25K account gates (H1 +$3.6k) but its trades lose R in every span at a fixed risk (a sizing-path effect, not an edge): rejected. The new discretion advisor scores every live and paper trade with these rules in dollars from now on.

## Links

- Family: [[Family management]]
- Day: [[Day 2026-10-29]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[lit-reversal-exit|LIT reversal exits]]
- Runs: `lit_struct_base, lit_struct_strail_15m_k1_any, lit_struct_runner_075_15m, lit_struct_runner_09_15m, lit_struct_choch_5m_k075_be, lit_struct_choch_5m_k1_exit, lit_struct_choch_15m_k1_exit, lit_struct_strail_5m_k1, lit_struct_tgt_cap_lit_r1.5, lit_struct_tgt_pool_lit_r3, lit_struct_tgt_cap_1h_r3, lit_`
- Source: `research/writeups/structure-management.md`
- Back to [[ZEUS Home]]
