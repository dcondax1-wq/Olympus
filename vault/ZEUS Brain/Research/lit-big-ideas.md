---
tags:
  - zeus/research
  - family/management
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-19"
status: "one adopt-candidate (scale-in on a 1m CISD after breakeven, with the stop moved to the add); trend-day mode and volatility sizing rejected; news-release setups not testable"
source: "research/writeups/lit-big-ideas.md"
aliases:
  - "LIT big ideas"
---

# LIT big ideas

> [!success] Verdict: adopt-candidate
> one adopt-candidate (scale-in on a 1m CISD after breakeven, with the stop moved to the add); trend-day mode and volatility sizing rejected; news-release setups not testable

**Full title:** LIT big ideas - scale-in after breakeven, a trend-day mode, volatility sizing, news-release setups

## Summary

Four ideas never tested on LIT were scored by the LIT rule (2026 only, pick on Jan-Jun, check on Jul-Oct; adopt only if both halves gain net $ AND MFFU 50K 2-week passes under the live sizing, two_week then safe_eval, $1.90, true 1m fills, stop before target in a bar). (1) Scale-in passes. After breakeven, wait for the first 1m pullback of at least 0.25R, then a 1m CISD close back up, and add the same number of micros at the next 1m open. The add uses the same breakeven stop and the same target, and its open risk is never above the first entry's $ risk, 60% of the room or the soft daily loss left. Once the add is +1 of its own risk, the whole position's stop moves to the add's price. Results: H1 net +$36,723 to +$49,205, H2 +$9,674 to +$26,015, 2-week pass 52.9 to 53.8 (H1) and 50.7 to 52.2 (H2), H2 fails unchanged at 2.9, H1 fails 9.2 to 10.1. Every neighbour holds in both halves (pullback 0.1-0.4R, add 0.75-1.5x, add fills up to 2 pts worse). The control (stop move with no add) does not. But the pass-rate gain is one eval start per half, and in H2 it rests on one trade, so the money is solid and the pass rate is thin. Starting at half size and adding at +1R cuts 2-week fails to 4.2 / 0.0%, but H1 loses $4.2k: rejected. (2) Trend-day mode: 0 of 16 H1-fitted classifiers held in H2. (3) Volatility tilts: 0 of 160 better in both halves. (4) News-release sweeps need a 94-395 pt stop: 0 trades in 2026 and in 2021-25. Engine option scale_in (default off; backtest only, the live route cannot send an add yet). Paper only.

## Links

- Family: [[Family management]]
- Day: [[Day 2026-10-19]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-live-fills|LIT live fills]]
- Runs: `lit_big_base, lit_big_scale_cisd, lit_big_scale_cisd_norat, lit_big_scale_ratchet_only, lit_big_scale_imm, lit_big_scale_half_imm, lit_big_trend_pick, lit_big_trend_all_be2, lit_big_vol_vix_hi15, lit_big_news_wide, lit_adopt_all3, lit_adopt_all3_eval, lit_adopt_t15_be_off, lit_adopt_t15_be_off_eval`
- Source: `research/writeups/lit-big-ideas.md`
- Back to [[ZEUS Home]]
