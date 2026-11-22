---
tags:
  - zeus/research
  - family/risk
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-19"
status: "adopt-candidate"
source: "research/writeups/lit-builder-25k.md"
aliases:
  - "MFFU Builder 25K next to the 50K"
---

# MFFU Builder 25K next to the 50K

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** MFFU Builder 25K next to the 50K - the 25K's rules, its eval sizing and copy trading both accounts with one LIT bot

## Summary

The owner is buying an MFFU Builder 25K ($63) to trade with the same LIT signals as the Builder 50K eval, with each account sized on its own room. Rules were re-checked on 2026-10-19 ($1,500 target, $1,000 EOD trailing max loss locking at +$100, $600 soft daily loss, 20 micros, no eval consistency rule, 1 min day, news allowed; the $600 daily loss is in the current guide, an older "legacy" 25K page says none). The 50K's config C scaled to the 25K passes 55% / 51% of evals within 2 weeks (H1 / H2), as fast as the 50K, and hardly ever fails outright. Its weak spot is different. About 12-16% of 25K evals end up "stuck": the room falls under $100, and even 1 micro on a 40-80 pt LIT stop would breach it, so the bot stops trading. The pick (H1) is 50% of the room instead of 60%, and safe_eval at 30% after session 10. It passes 54% / 48% in 2 weeks, 79% / 77% in the end (Monte Carlo), and is dead (failed or stuck) in 10 sessions 11% / 4%. That is $117-132 per 2-week pass and about $80 per eventual pass at $63, against $174-181 and $115-119 on the 50K. Copy trading on the same day is close to one bet: when one account passes, the other almost always does too (correlation 0.92-0.95). Both pass in 2 weeks about 50% of the time, and both die about 7-10% (MC H1 / H2 6.8 / 6.4%). Starting the 25K one week later decouples them: at least one passes in its own 2 weeks 68-76% of the time instead of 55%, and both die only 2-3%. Funded 50K + 25K at the H2 rate is about $1,015 a month of payouts, or $780 a month net over the first 6 months including fees and the eval time. Copying between your own MFFU accounts is reported as allowed by third parties. MFFU's own fair-play page only forbids copying that "coordinates trades for an unfair advantage" and copying other people, so ask support in writing. The live code cannot run a 25K yet, because live.py sizes every account on the 50K's plan. Paper only; nothing live was changed.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-19]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-funded-firms|LIT on 3 funded accounts]]
- Runs: `lit_25k_rec, lit_25k_c_scaled, lit_25k_copy, lit_2wk_rec, lit_ff_mffu_builder_25k`
- Source: `research/writeups/lit-builder-25k.md`
- Back to [[ZEUS Home]]
