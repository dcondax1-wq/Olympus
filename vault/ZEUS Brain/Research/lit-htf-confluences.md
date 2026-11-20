---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "promising"
source: "research/writeups/lit-htf-confluences.md"
aliases:
  - "LIT higher-time-frame confluences"
---

# LIT higher-time-frame confluences

> [!tip] Verdict: promising
> promising

**Full title:** LIT higher-time-frame confluences - draw on liquidity, dealing ranges, PO3, bias, structure, HTF FVGs and time of week, deep dive

## Summary

The owner asked for a deep dive into higher-time-frame (HTF) context. Every 2026 LIT setup (330 setups, 176 that would fill alone, 120 taken) got 42 causal HTF facts, read as 49 HTF confluences (1H, 4H, daily and weekly candles built from the CME NQ1! 5m file; look-ahead test 30 of 30 identical) plus 26 LIT facts. 75 confluences were scored in Jan-Jun (pick) and Jul-Oct (check), with permutation p-values and a multiple-testing correction. Nothing survives the correction, and the number that "hold in both halves" (18 of 65) is exactly what chance gives (17.7). The owner's main idea, trading WITH the HTF draw, flips between the halves and loses money as a filter, as a London-only filter and as a size rule. 86,000 2- and 3-way combinations were tried: the HTF-only ones picked on Jan-Jun held in Jul-Oct 0 times out of 22. Skipping setups never works (below 2 trades a week). Three small size tilts help both halves and are adopt-candidates at low confidence. (1) The 4H draw, size-neutral: 1.4x when the nearest unswept 4H swing is on the target side, else 0.8x. It is the only rule that raises the 2-week pass in both halves (H1 37.5% -> 42.2%, H2 29.5% -> 34.6%; cost per 2-week pass $245 -> $218 and $311 -> $265), but Jul-Oct 1-month fails go from 0% to 10.3%. (2) The fresh trap times a clear HTF path: H1 2-week pass 52.3%, H2 unchanged at 29.5%, +$10.3k / +$1.5k. (3) A clear 1H path (no opposing 1H FVG before the target): H1 41.4%, H2 unchanged, +$6.6k / +$0.4k. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-losses|LIT losses]], [[lit-report-coverage|LIT report coverage]], [[lit-strategy|LIT]], [[lit-trade-selection|LIT trade selection]], [[lit-untested-targets|LIT untested target and exit ideas]]
- Runs: `lit_htf_draw4h_neutral, lit_htf_trap_x_clearlv, lit_htf_clear1h_size, lit_htf_trap_x_clear1h, lit_htf_clearlv_size, lit_htf_clearpath_size, lit_htf_trap_x_draw4h, lit_htf_draw4h_size, lit_htf_draw4h_london, lit_htf_with_draw_size, lit_htf_with_draw_london, lit_htf_against_skip, lit_htf_pdbos_london,`
- Source: `research/writeups/lit-htf-confluences.md`
- Back to [[ZEUS Home]]
