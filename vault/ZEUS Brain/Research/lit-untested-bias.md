---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "rejected - nothing adopted (VIX >= 20 upsizing is a NEUTRAL \"can't check yet\")"
source: "research/writeups/lit-untested-bias.md"
aliases:
  - "LIT untested bias and regime ideas"
---

# LIT untested bias and regime ideas

> [!failure] Verdict: rejected
> rejected - nothing adopted (VIX >= 20 upsizing is a NEUTRAL "can't check yet")

**Full title:** LIT untested bias and regime ideas - VIX regime size, target-aware eval size, weekly profile, Asia range gate, event days

## Summary

39 variants of five bias / regime ideas were tested on the live LIT trades (CME NQ1! 5m + true 1m bars, 2026), each picked on Jan-Jun and checked on Jul-Oct, at the live eval sizing ($800 up to a 25-pt stop, 60% room cap). Same setups, entries, stops and targets; only which setups are taken or the size changes. None is adopted. Upsizing when the prior VIX close is 20 or more (x1.5) adds +$5.3k in H1 and +$1.4k in 2021-25, but Jul-Oct 2026 had one VIX day >= 20 and no trade on it, so it cannot be checked out of sample (NEUTRAL). The weekly-profile skip (Thu/Fri, no trade toward a week high or low made Tue-Wed) looks better in both halves on the eval path (+$2.7k / +$0.8k), but at a fixed size it loses $2.1k in H1 (it skips a +$2.4k winner) and the H1 pass rate falls from 92% to 85%: rejected. Target-aware eval sizing, the Asia range gate, OPEX / month-end / quarter-end days and VIX < 15 downsizing are rejected. Big-tech earnings days could not be tested (no earnings dates in data/news/events.csv). Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_u_bias_base, lit_u_bias_vix_ge_20_x1_5, lit_u_bias_vix_ge_22_x1_5, lit_u_bias_vix_ge_18_x1_5, lit_u_bias_vix_lt_15_x0_75, lit_u_bias_tgt_trim_x1_0, lit_u_bias_tgt_press_roomge1500_tgtle4r, lit_u_bias_tgt_trim_plus_press_roomge2000_tgtle4r, lit_u_bias_wp_tw_skip_toward, lit_u_bias_wp_how_skip_tow`
- Source: `research/writeups/lit-untested-bias.md`
- Back to [[ZEUS Home]]
