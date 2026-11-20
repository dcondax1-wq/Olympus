---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-tight-stops-size.md"
aliases:
  - "LIT tight stops and bigger size"
---

# LIT tight stops and bigger size

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT tight stops and bigger size - do we need 50-60 point stops, and what if we trade more micros or 1 NQ?

## Summary

On the exact live LIT signals (120 trades in 2026), 48 stop and entry variants were tested, each at 12 sizes, with the MFFU 50K eval simulated. Tighter stops do not help. The 1m protected-swing stop (median 14-17 pts instead of 44-52) looks great in Jan-Jun only because the size rule then risks about 2.7 times more money. At the same $ a trade it wins Jan-Jun and loses Jul-Oct: winners win less often (23% to 13%) because many turn into breakeven scratches, and 2021-25 loses money. Skipping wide stops leaves 0.1-1.2 trades a week. Limit entries on the 1m retest miss the best winners. The speed has to come from size on the live sweep-extreme stop, with a cap that never risks more than 60% of the room to the max-loss floor. $800 up to a 40-pt stop + that cap passes 47% of evals within 2 weeks in both halves (live 29% / 23%), with 5% failing within 2 weeks. $800 up to a 25-pt stop + the cap keeps the live pass rate (92% / 96%) and passes faster (2-week pass 37.5% / 29.5%). 1 NQ fixed fails 28-38% of evals within 2 weeks. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-experiments|LIT experiments]]
- Runs: `lit_tight_live_ref, lit_tight_eval_fast_room60, lit_tight_eval_800_25_room60, lit_tight_eval_1000_20_room60, lit_tight_funded_800_25, lit_tight_tap_lit, lit_tight_tap_flat800, lit_tight_ext_flat800, lit_tight_frac50_flat800, lit_tight_cap25_skip, lit_tight_cap30_tap, lit_tight_entry_ob, lit_tight_ex`
- Source: `research/writeups/lit-tight-stops-size.md`
- Back to [[ZEUS Home]]
