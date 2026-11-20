---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected"
source: "research/writeups/lit-adv-audit-smt.md"
aliases:
  - "LIT advanced report ch.7 audit"
---

# LIT advanced report ch.7 audit

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT advanced report ch.7 audit (clocks, bar edges, unresolved records) and experiment 5 (NQ/ES divergence at the same event)

## Summary

The owner's LIT Advanced Decisions Report asks whether clocks, candle edges and missing data bend the backtest. On the 120 LIT trades of 2026 they barely do. With 1m bars the entry is at a bar's open, so no stop or breakeven exit shares a bar with the target. Every fixable item together (a stop bar that opened through the stop, 50 missing 1m minutes in 9 trades, the 15:55 flat clock, the early-close holidays) moves 2026 by about -$500 of +$41,734, mostly in H1. The real distortion is in the eval scoring. Starts near the end of a span cannot see 10 or 20 sessions, which inflates H2's quoted 2-week pass rate at the LIT size (23.1% vs 17.4% on full windows; 1 month 44.9% vs 32.2%). runlib now has a switch for that, off by default. Experiment 5 (NQ takes a level while ES holds its same-time copy, or the reverse), used as a size multiplier and judged under the live two_week sizing, is rejected. The divergence trades are not better, and the two rules that gain in both halves (+$350 / +$430-510) do worse than sizing up random trades. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-adv-continuation|LIT advanced report ch2-4]], [[lit-htf-confluences|LIT higher-time-frame confluences]], [[lit-live-fills|LIT live fills]], [[lit-losses|LIT losses]], [[lit-report-tests|LIT report tests]], [[lit-untested-entries|LIT untested entry ideas]]
- Runs: `lit_live, lit_adv_audit_gap5m, lit_adv_div_nqonly_x1p25, lit_adv_div_nqonly_x1p25_both_x0p75, lit_adv_div_nqonly_x0p75, lit_adv_div_rev_x1p25, lit_adv_div_rev_x0p75, lit_adv_div_div_x1p25, lit_adv_div_nodiv_x0p75`
- Source: `research/writeups/lit-adv-audit-smt.md`
- Back to [[ZEUS Home]]
