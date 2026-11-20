---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
  - bot/zlarior
  - bot/atlas
  - bot/blitz
type: "research"
date: "2026-11-18"
status: "finding (no change). 4 rules from the anatomy tested on the real backtests, 0 pass; all 4 registered in the ZEUS Lab (re-tested every night)"
source: "research/writeups/win-loss-anatomy-2026-11-18.md"
aliases:
  - "Why we win, why we lose"
---

# Why we win, why we lose

> [!info] Verdict: finding
> finding (no change). 4 rules from the anatomy tested on the real backtests, 0 pass; all 4 registered in the ZEUS Lab (re-tested every night)

**Full title:** Why we win, why we lose (2026-11-18) - every Zlarior, ATLAS and BLITZ trade taken apart; the losers are mostly good trades that lost, a careful human's skip list costs money, 0 of 4 rules pass

## Summary

Owner - "See why our losses lose for strategies. And why they win. I expect all of our strategies to be better." Every trade of the repo's own backtests (costs in) was taken apart - Zlarior 631 (run lit_live, 2026 on 1m), ATLAS 1,288 account trades, BLITZ 2,198 - with MAE / MFE in R and $ and the minutes to each, exit, session, weekday, VIX band, ranges, gaps, prior-day levels, daily and 1h trend, chop, news, ES and what came after the exit. Losers mostly never worked (Zlarior 62% of 2026's lost $, ATLAS 58%, BLITZ 72%); real shake-outs are rare (a 50% wider stop would have won 0-9% of Zlarior / ATLAS stop-outs); nothing known at the entry separates losers from winners better than chance; a pre-declared careful-human checklist would have skipped as many winners as losers (Zlarior -$4,320 Jan-Jun / -$5,518 Jul-Oct, ATLAS -$13,732 / -$2,570). Four rules (Zlarior trend-pullback x1.25 and checklist skip, ATLAS London-open x1.25 and checklist skip) all fail the adopt bar. Nothing changes.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]], [[BLITZ (paper)]]
- Refers to: [[2026-11-15-atlas-deep|ATLAS deep edge]], [[2026-11-15-lit-deep|LIT deep edge]], [[blitz-25k|BLITZ on its own MFFU Builder 25K]], [[lit-edge-2026-10-30|Zlarior edge night]], [[lit-losses|LIT losses]], [[structure-management|Trade like a person]]
- Runs: `research/anatomy/ (trades_lit / trades_atlas / trades_blitz.json, explain.json, rules.json); tools/win_loss_anatomy.py; ZEUS Lab ids lit_anat_pullback_x1.25, lit_anat_checklist_skip, atlas_anat_london_open_x1.25, atlas_anat_checklist_skip`
- Source: `research/writeups/win-loss-anatomy-2026-11-18.md`
- Back to [[ZEUS Home]]
