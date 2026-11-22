---
tags:
  - zeus/research
  - family/data
  - verdict/info
type: "research"
date: "2026-10-23"
status: "info"
source: "research/writeups/data-official.md"
aliases:
  - "Official data only"
---

# Official data only

> [!note] Verdict: info
> info

**Full title:** Official data only - roll gaps, ES files, daily bars and VIX rebuilt from official sources

## Summary

Owner 2026-10-23 - "we only use official data". Every price file is now TradingView CME exports (NQ1!, MNQ1!, ES1!) and VIX / VXN come from CBOE's own files. Two NQ roll gaps were measured with non-official quotes and are now official estimates (Sep-26 294.75 session-open jump, was 295.75; Jun-26 289.25 carry model, was 254.75), so NQ bars move +33.5 pts before 2026-06-14 18:00 ET and -1.0 pt to 2026-09-14 18:00 ET (later bars unchanged). ES needed no truncation (the 5m set was already 100% ES1!), but two ES roll gaps change by -1.75 and -0.25 pts, the ES 1m file is gone and NQ/ES daily files are rebuilt from the official 5m. LIT 2026 +$43,385 -> +$43,394 (7 target-hit trades move by cents to $3.48), eval pass/fail unchanged; 2021-25 +$1,211 -> +$1,265 (one extra breakeven trade). Every test passes.

## Links

- Family: [[Family data]]
- Day: [[Day 2026-10-23]]
- Refers to: [[lit-bias-discretion|LIT with bias and discretion]], [[lit-more-setups|LIT more setups a week]]
- Runs: `lit_live, lit_adopt_t15_be_off, lit_adopt_t15_be_off_eval, lit_adopt_all3, lit_adopt_all3_eval, lit_more_ent_asia_slot_rr3, lit_more_ent_asia_slot_rr3_eval`
- Source: `research/writeups/data-official.md`
- Back to [[ZEUS Home]]
