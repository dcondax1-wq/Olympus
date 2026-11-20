---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-1m-management.md"
aliases:
  - "LIT on the 1-minute chart"
---

# LIT on the 1-minute chart

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT on the 1-minute chart - smarter entries and "this trade is wrong" exits, tested like a person would trade them

## Summary

The owner asked for 1-minute entries and loss management that thinks like a person. On the exact live LIT signals (2026, true 1m bars, eval sizing $800 up to a 25-pt stop + the 60% room cap), 153 variants were tested, picked on Jan-Jun and checked on Jul-Oct. 1m entry filters (inner 1m inducement, 1m displacement, volume, absorption, patience, pullback entries) all lose money in both halves. The classic "trade is wrong" signals (1m CISD against, a new 1m low, back inside the swept level, higher low taken, a volume surge against) do cut 50-100% of the losers early, but they also kill 30-80% of the winners. In Jul-Oct the winners dip as deep as the losers before they run (median 0.54R against), so every one of these signals loses money there. One signal is real in both halves: ES not confirming. When ES closes a 5m bar beyond its own sweep extreme and NQ then prints a 1m CISD against, before the trade has reached +0.75R, exit at the next 1m open. It cut 8 of 53 losers at about half a loss and touched no winner: H1 +$446, H2 +$1,514. That is small and rests on 8 trades. Profit rules (structure trail, closing at the 18:00 or midnight open on a stall, skipping breakeven on fast moves) do not hold in both halves. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_1m_base_eval, lit_1m_es_exit, lit_1m_o18_stall, lit_1m_halfcut_cisd, lit_1m_cut_cisd, lit_1m_cut_newlow, lit_1m_cut_accept, lit_1m_cut_hl, lit_1m_cut_volsurge, lit_1m_idm1_req, lit_1m_disp1_half, lit_1m_absorb_half, lit_1m_patience, lit_1m_pullback, lit_1m_bos_trail, lit_1m_fast_be`
- Source: `research/writeups/lit-1m-management.md`
- Back to [[ZEUS Home]]
