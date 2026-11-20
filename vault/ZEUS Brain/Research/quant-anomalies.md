---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
type: "research"
date: "2026-10-23"
status: "rejected"
source: "research/writeups/quant-anomalies.md"
aliases:
  - "Quant anomalies on CME NQ"
---

# Quant anomalies on CME NQ

> [!failure] Verdict: rejected
> rejected

**Full title:** Quant anomalies on CME NQ - do the published index-futures edges exist in 2021-26?

## Summary

Owner (2026-10-23) - "What about quant, could you learn that?" Yes, and I tested the textbook quant edges on our own CME NQ bars - intraday momentum (Gao et al. 2018), overnight drift, turn of the month, pre-FOMC drift (Lucca-Moench 2015), pre-holiday, daily reversal, gap fill / gap-and-go, VIX level and term-structure regimes, end-of-day momentum (Baltussen et al. 2021) and volatility-targeted sizing (Moreira-Muir 2017). 31 variants, all fixed before the run. None is real on NQ 2021-26 - 2 of 31 pass a 5% placebo test in 2021-24 (luck alone gives about 1.6), none survives the family-wise check, and both fade out of sample. Pre-FOMC drift was strong in 2021-24 (+93 pts a micro per meeting, placebo p 0.01) and gone in 2025-26 (-6 pts on 14 meetings). The textbook intraday momentum has the wrong sign (t -2.0). Volatility targeting makes LIT's eval odds worse in every version (2-week pass H1 57.1% to 24-54%, H2 52.2% to 39-46%) and ATLAS's too. The tilts and a separate quant slot do not help either. No quant overlay goes on LIT or ATLAS. One thing to watch, not to trade - since 2025 the last half hour has tended to reverse the day's move on both NQ and ES.

## Money first

| effect | on NQ 2021-26 |
|---|---|
| Intraday momentum (first 30 min -> last 30 min) | **dead**: wrong sign in sample, flat out of sample |
| Overnight drift | **the shape exists** (the night carries the rise), **not tradable**: no better than a random window, lost in 2026 H2 |
| Turn of the month | **dead in sample**, positive 2025-26 on 22 events (watch only) |
| Pre-FOMC drift | **existed 2021-24**, **gone 2025-26** |
| Pre-holiday | **dead** (few events, mixed) |
| Daily reversal / momentum | **dead** (flips year to year) |
| Gap fill / gap-and-go | **dead** |
| VIX level / term-structure regime | **dead** (no better than buy and hold) |
| End-of-day momentum | **dead** as published; a recent **reversal** on NQ and ES since 2025 is a lead only |
| Volatility-targeted size on LIT / ATLAS | **rejected**: worse eval odds in every version |

**Family-wise:** 31 variants, 2 with in-sample placebo p < 0.05 (eod_hour 0.010, pre_fomc 0.012) against about 1.6
expected from luck. 0 survive Holm, and 0 pass the out-of-sample check.

**What "learning quant" means for this bot.** The published edges are a few points a trade. On a micro they sit next to
1.45 pts of costs, and they have mostly faded since they were published. LIT's edge is in its setup, not the calendar
or the clock. The honest quant toolkit (placebos, family-wise counting, out-of-sample halves) is now in
`tools/quant_anoms.py`. It can be reused for any new idea.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-23]]
- Runs: `q_im_textbook, q_im_60, q_im_rth30, q_im_mag, q_im_vix, q_on_1600, q_on_1800, q_id_rth, q_on_after_down, q_on_mon, q_on_tue, q_on_wed, q_on_thu, q_on_fri, q_tom, q_tom_1, q_pre_fomc, q_pre_fomc_rth, q_pre_holiday, q_rev1, q_rev2, q_rev5, q_gap_fill, q_gap_go, q_gap_fill_small, q_bh_cc, q_vreg_level,`
- Source: `research/writeups/quant-anomalies.md`
- Back to [[ZEUS Home]]
