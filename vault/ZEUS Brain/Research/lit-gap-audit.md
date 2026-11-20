---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
  - lane/combo50k
type: "research"
date: "2026-10-20"
status: "rejected - nothing new to switch on; the midday profit take is still a small candidate (promising), it improves every eval number except the back-to-back path money"
source: "research/writeups/lit-gap-audit.md"
aliases:
  - "LIT gap audit"
---

# LIT gap audit

> [!failure] Verdict: rejected
> rejected - nothing new to switch on; the midday profit take is still a small candidate (promising), it improves every eval number except the back-to-back path money

**Full title:** LIT gap audit - every LIT idea tested so far, what was still untested, and the top 10 untested ideas run on live LIT and on the combo

## Summary

All 36 LIT write-ups, the report-2 inventory and the 584 LIT runs were read and turned into one table of the ideas already tested (about 130 ideas in 40 study families). 22 LIT / ICT / SMC ideas had never been tested, or never on the real eval path. The top 10 were built as default-off engine options (engine/lit.py) and run as 96 variants, each on live LIT and on the adopt-candidate combo (t_check + scale_in + be_off), 192 runs, picked on Jan-Jun 2026 and checked on Jul-Oct 2026, with money on the real MFFU 50K eval path (two_week sizing, $1.90 a micro). None passes every gate. Killzone-specific settings, ATR stop limits, a maximum sweep depth, Asia-range deviation targets, Monday / 20-day levels (turtle soup), London time exits, re-entry after a breakeven, a 2nd 1m CISD entry, the 09:30 opening model and the failed-zone flip all lose money in a half, raise 2-week fails or rest on a handful of trades. The closest is the midday profit take (out at 12:00 ET when the trade is +0.5R or more): more money at the LIT size in both halves on both bases, a higher 2-week pass rate in both halves, the same fails, more $ per eval, but the back-to-back eval path makes less in H1 (path noise on 7 changed trades). Paper only; live_model.json unchanged.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-20]]
- Strategies: [[Zlarior (LIT)]], [[50K combo]]
- Runs: `lit_gap_kz_live, lit_gap_kz_combo, lit_gap_satr_live, lit_gap_satr_combo, lit_gap_dmax_live, lit_gap_dmax_combo, lit_gap_sd_live, lit_gap_sd_combo, lit_gap_lvl_live, lit_gap_lvl_combo, lit_gap_tx_live, lit_gap_tx_combo, lit_gap_rebe_live, lit_gap_rebe_combo, lit_gap_nth_live, lit_gap_nth_combo, lit_`
- Source: `research/writeups/lit-gap-audit.md`
- Back to [[ZEUS Home]]
