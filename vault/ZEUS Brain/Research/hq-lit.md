---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-23"
status: "adopt-candidate"
source: "research/writeups/hq-lit.md"
aliases:
  - "HQ LIT"
---

# HQ LIT

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** HQ LIT - can LIT win more often without losing its payoff? Exits, A+ grading and the OFF switches re-scored

## Summary

The owner asked for 2+ trades a week, high quality, high probability, high profit. Three things were tested on today's live LIT (2026 H1 pick, H2 check, 2021-25 reference, $1.90 a micro + 1 tick, eval path = live two_week sizing). (1) Exits, 93 variants on the engine's own trades, re-walked exit for exit (631/631 equal to the engine). That includes the partial at 1R that could not be measured before. No exit raises the win rate without losing money. A 50% partial at 1R costs 37% of H1 and 42% of H2 ($21.4k / $5.4k vs $33.7k / $9.4k) and drops the H2 2-week eval pass from 52% to 15%. Not one trade moves above +0.5R, because the runner then mostly stops at breakeven. Trailing, earlier or later breakeven, structure breakeven and time exits all lose money or eval odds. LIT's edge is the far VIX-band target, and the live exits are already the best of the 93 in H1. (2) An A+/B/C grade from facts known at the fill: a pre-registered textbook checklist, a grade fitted on H1, and the single best H1 feature. None beat a random-grade placebo in H2 at 95%. Each one reverses in 2021-25. The best lead is the fresh-inducement size-up (A x1.5 when the nearest inducement is <= 6 bars old): H2 86th percentile vs placebo, 2021-25 11th, eval H2 2-week pass 52.2 -> 50.7. Not adopted. (3) The six OFF switches, alone and in all 64 combinations. Ranked by H2 money: scale_in (+$5.7k LIT rule, +$8.2k eval path, eval odds kept, bootstrap p = 0.004), the Asia slot (+$4.1k / +$3.3k, but 2-week fails 0 -> 2.9% and 2021-25 -$18k), how_out (eval +$1.7k but the LIT rule -$11.4k in H1), wk_loss_usd 1200 / room_f 0.55 / cisd1m 22 (money-neutral; together they cut the H1 2-week fails 5.9% -> 0.0%). Best combination on H1 = scale_in + room_f 0.55 + wk_loss_usd 1200. H1 eval +$53.6k, 2-week 57.1/0.0, 1 month 78.9/2.8. H2 check +$14.7k vs +$9.1k, 2-week 52.2/0.0, 1 month 52.5/1.7. Without scale-in (it still waits for the owner's Sim roundtrip): cisd1m 22 + room_f 0.55 + wk_loss_usd 1200, H1 2-week fails 5.9 -> 0.0, H2 +$9.8k. Recommended: the safety pair (room_f 0.55 + wk_loss_usd 1200) and cisd1m 22 now, and scale_in after the Sim check.

## Money first

- **Exits: keep today's.** The partial at 1R costs 37-42% of the money and most of the eval odds. No exit raises the true
  win rate without paying for it, roughly $400-$1,000 of H1 for every point of win rate.
- **A+ grading: not adopted.** None of the three grades beats a random grade in H2 at 95%. All reverse in 2021-25, and they
  lower the eval pass. The fresh-inducement (<= 6 bars) size-up stays a paper lead.
- **Switches, recommended (your OK needed; nothing was changed):**
  1. **Now, safety pair + insurance:** `room_f 0.55` + `wk_loss_usd 1200` + `cisd1m 22`. H1 2-week fails 5.9% -> 0.0% and
     1-month fails 11.9% -> 5.5%, with the same passes. H2 unchanged (52.2 / 0.0) and +$0.7k. Price: about $4.4k less H1
     eval-path money (smaller trades after a -$1,200 week).
  2. **After the Sim roundtrip** (`python -m engine.ninjatrader --sim-roundtrip-add` on Sim101): `scale_in`. With 1, this
     is the study's pick: H2 +$14.7k vs +$9.1k on the eval path and +$15.1k vs +$9.4k on the LIT rule ($4,060 a month vs
     $2,530), with the same 2-week odds.
- **Not recommended:** the Asia slot (fails up, 2021-25 -$18.6k), `how_out 0.5` (H1 -$11.4k on the LIT rule), every partial
  / trail / earlier BE, the time exit, and every grade.
- **About "2+ a week with high probability":** LIT gives 2.6-3.1 trades a week with about 1 in 4 to 1 in 3 real winners at
  +3.7-5.3R. That is its nature. A high-win-rate strategy would need a different, near target. On this data that loses the
  money (fixed 2R target in the ablation: -$16.6k H1). The honest version of "high probability" here is the eval: a
  **57% / 52% chance to pass within 2 weeks with a 0% chance to fail** (with the safety pair).

### Switch JSON (for the owner's decision only; NOT applied)

1 (now), in `live_model.json` **and** `live_model_lit.json`:

```json
"lit": { ..., "cisd1m": 22 },
"lit_sizing": { ..., "wk_loss_usd": 1200, "two_week": { ..., "room_f": 0.55 } }
```

2 (after the Sim roundtrip passes), inside "lit" in both files:

```json
"scale_in": {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}
```

After switching: rerun `python tools/lit_losses.py live` and the dashboard data (CLAUDE.md "Switch one off/on").

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-23]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-ablation|LIT ablation]], [[lit-big-ideas|LIT big ideas]], [[lit-more-entries|LIT more entries]], [[lit-trade-selection|LIT trade selection]]
- Runs: `hq_lit_live, hq_lit_live_eval, hq_lit_p1_50, hq_lit_p1_50_eval, hq_lit_p2_33, hq_lit_p2_33_eval, hq_lit_be_none, hq_lit_be_none_eval, hq_lit_be_sw1, hq_lit_be_sw1_eval, hq_lit_tr2_5m, hq_lit_tr2_5m_eval, hq_lit_tx120_0, hq_lit_tx120_0_eval, hq_lit_tc_mfe07, hq_lit_tc_mfe07_eval, hq_lit_grade_textboo`
- Source: `research/writeups/hq-lit.md`
- Back to [[ZEUS Home]]
