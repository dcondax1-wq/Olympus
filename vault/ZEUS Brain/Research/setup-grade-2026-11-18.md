---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-18"
status: "rejected (no change, no proposal). 4 pre-declared versions per strategy + 7 single checks; 1 Zlarior version passes the money gate in all three periods but not the luck test (2021-25 p 0.37) and ..."
source: "research/writeups/setup-grade-2026-11-18.md"
aliases:
  - "Setup grade"
---

# Setup grade

> [!failure] Verdict: rejected
> rejected (no change, no proposal). 4 pre-declared versions per strategy + 7 single checks; 1 Zlarior version passes the money gate in all three periods but not the luck test (2021-25 p 0.37) and flips with small definition changes; 0 ATLAS versions pass. ZEUS Lab ids setup_grade_lit / setup_grade_atlas (kind setup_grade, Rejected). live_model*.json, second_model.json, engine/ untouched.

**Full title:** Setup grade (2026-11-18) - a calm trader's 7-warning checklist (A / B / C) before every Zlarior and ATLAS signal; grading by the chart does not pick winners, smaller B trades cost money, skipping only the worst pile-ups is a small maybe for Zlarior (could be luck), a loss for ATLAS. Nothing changes.

## Summary

Owner - "More accurate with our trades, don't trade like a bot, trade how a person would, without emotion." Built the checklist a calm discretionary NQ trader asks before each signal, from what is on the chart at that moment only (never the last trade's result): higher-timeframe trend against, a key level within half a stop toward the target, day already extended, inside day (chop), big news in 30 min, ES against, VIX not normal. A = fewer warnings than a typical setup, B = typical, C = more. Checks, weights (1 each) and the cut fixed on Jan-Jun 2026 only; judged untouched on Jul-Oct 2026 and 2021-25, costs in, day / slot left free after a skip. Zlarior, skip C (3+ of 7): +$712 / +$303 / +$11 a month at the Zlarior size, eval path +$124 / +$824 / +$46, 2-week pass 44.5 -> 46.2% / 39.1 -> 47.8%, but random skips of as many setups do as well in 2021-25 (p 0.37; Jul-Oct p 0.16) and it turns into a loss with the first-draft level distance or a stricter C. A full / B half / C skip loses (-$188 / -$1,518 a month). The Jan-Jun-picked grade (trend + level + chop) loses -$592 / -$1,711. ATLAS: every version loses on the funded 25K in Jul-Oct (-$142 a month for skip C). The single check that helped most is the key level in the way, and even it loses money on its own.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Refers to: [[win-loss-anatomy-2026-11-18|Why we win, why we lose]]
- Runs: `none (research/lab/setup_grade.json; tools/setup_grade.py; tests/test_setup_grade.py)`
- Source: `research/writeups/setup-grade-2026-11-18.md`
- Back to [[ZEUS Home]]
