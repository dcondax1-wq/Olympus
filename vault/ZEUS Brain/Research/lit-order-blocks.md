---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-order-blocks.md"
aliases:
  - "LIT order blocks"
---

# LIT order blocks

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT order blocks - finding them like a LIT/ICT trader, and every way to trade them with LIT

## Summary

A new order-block detector (engine/lit_ob.py, no look-ahead, checked on 20 charts) finds the last opposite candles before a displacement that breaks structure and leaves a fair value gap, on 5m, 15m, 1H, 4H and daily candles, with mitigation, breakers, extreme vs decisional blocks and the owner's mitigation rules. It was put into the live LIT trade in every role - point of interest, entry, target, obstacle, and as a source of new trades (sweep into or inside a fresh 1H/4H/daily block, also as a second trade a day) - and scored with both live sizes (eval and two_week), picked on Jan-Jun 2026 and checked on Jul-Oct 2026. Nothing improves both halves, so nothing goes live. The reason is simple: only 10-25 of the 120 live trades sweep into a fresh higher-timeframe block, those trades are not better than the rest in Jan-Jun, and fresh HTF blocks that LIT could trade on its own add 1-16 trades a year. Two ideas are worth watching: skipping trades with a fresh opposing 15m/1H block less than 2R away halves the 2-week eval fails (H1 8.4% to 3.4%, H2 2.9% to 0%) but costs about $4.5k-6k in Jan-Jun and does not raise Monte Carlo passes; HTF block setups as a second trade a day add about 10 trades and a little money in both halves but leave the Jul-Oct 2-week pass flat (50.7% to 49.3%). Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_ob_base, lit_ob_poi_require_15m_1h_4h_body, lit_ob_poi_require_loose_15m_1h_4h_1d, lit_ob_poi_x1_5_when_present, lit_ob_poi_skip_when_3_atr_from_any_fresh_htf_ob, lit_ob_ch12_poi_x1_5_all_origin_checks, lit_ob_entry_5m_ob_mean_threshold_tap_1m_cisd_if_within, lit_ob_entry_1m_ob_mean_threshold_af`
- Source: `research/writeups/lit-order-blocks.md`
- Back to [[ZEUS Home]]
