---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-21"
status: "rejected (no adopt-candidate); two small leads to watch (MACD 15m divergence instead of the inducement, 15m demand/supply retest)"
source: "research/writeups/lit-retail-entries.md"
aliases:
  - "LIT retail entries"
---

# LIT retail entries

> [!failure] Verdict: rejected
> rejected (no adopt-candidate); two small leads to watch (MACD 15m divergence instead of the inducement, 15m demand/supply retest)

**Full title:** LIT retail entries - support/resistance, supply/demand, break-and-retest, EMA pullbacks and MACD divergence as new LIT trades

## Summary

The owner asked whether big retail tools (EMAs, supply and demand, support and resistance, MACD) can add LIT trades to reach 3+ a week. 47 new setups were built (engine/lit_retail.py, closed bars only, checked with data cut at the entry) and each ran through the exact live LIT trade (1m CISD entry, stop 1 tick beyond the structural extreme, VIX-band target, BE, 15-min check, Monday rule, weekly stop), in 3 ways next to LIT (first fill wins, a second slot on LIT-free days, a 2nd trade a day) = 141 combined tests, picked on Jan-Jun 2026 and checked on Jul-Oct, money at the LIT size rule ($1.90/micro) and the MFFU 50K eval under the live two_week sizing. None passes. Only 10 of 141 add money in both halves (about 12 expected by chance) and none of those reaches 3 trades a week in Jul-Oct without raising the eval fail rate. The pick on Jan-Jun, EMA pullback (15m EMA 21) as a 2nd trade, makes +$13.0k in H1 and loses -$3.7k in H2 (its own trades win 25% in H2, 1-month eval fails 0% -> 24%). As extra sweep levels, S/R clusters, round numbers and S/D zone edges add only 0-6 trades a half: LIT's own levels already cover them. The closest call, 15m supply/demand retest + MACD 15m divergence in place of the inducement as a 2nd trade, gives 3.75 / 3.27 trades a week and +$4.7k in H1 but -$35 in H2 with 2-week fails 0% -> 2.9%. Built default off (lit option "retail", "src_cap"); live loop parity 147/147 with it on. Nothing changes in live_model.json.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-21]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-adv-continuation|LIT advanced report ch2-4]], [[lit-all-hours|LIT all hours]], [[lit-batch3a|LIT batch 3a]], [[lit-batch3b|LIT batch 3b]], [[lit-more-setups|LIT more setups a week]], [[lit-new-entries|LIT new entries and confluences]], [[lit-order-blocks|LIT order blocks]]
- Runs: `lit_retail_e_base_live_lit, lit_retail_e_brt_pdh_l_only_second, lit_retail_e_brt_sr15_1h_disp_0_8_second, lit_retail_e_brt_sr15_1h_pdh_l_second, lit_retail_e_brt_sr15_1h_second, lit_retail_e_brt_sr15_1h_tol_0_5_second, lit_retail_e_brt_sr1h_second, lit_retail_e_ema_pb_15m21_alone, lit_retail_e_ema_p`
- Source: `research/writeups/lit-retail-entries.md`
- Back to [[ZEUS Home]]
