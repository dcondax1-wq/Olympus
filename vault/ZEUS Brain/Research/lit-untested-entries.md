---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "adopt-candidate"
source: "research/writeups/lit-untested-entries.md"
aliases:
  - "LIT untested entry ideas"
---

# LIT untested entry ideas

> [!success] Verdict: adopt-candidate
> adopt-candidate

**Full title:** LIT untested entry ideas - buy-stop entry, chasing a missed limit, ES SMT, and a LIT opening model

## Summary

Four entry ideas nobody had tested on LIT were run on the exact live LIT signals with the live eval sizing, 33 variants, picked on Jan-Jun 2026 and checked on Jul-Oct 2026. Three are rejected - a buy-stop above the 1m CISD candle (H2 -$4.8k), chasing a missed limit on a 1m pullback (H1 -$4.6k), and ES SMT as a size boost, a filter or an early 1m trigger (H2 -$0.6k to -$11.6k). One passes the rule, barely - the LIT opening model on the overnight high/low (a 09:30-10:00 sweep of the 18:00-09:30 range, inducement taken first, 1m CISD, entry by 10:00 as an extra setup on days the bot has not traded yet). It adds +$1,589 in Jan-Jun and +$839 in Jul-Oct at 3.4 / 3.0 trades a week and keeps the eval pass rate about the same (91% / 95% vs 92% / 96%). It rests on only 13 trades in 2026 (3 winners), and letting the entry run to 10:15 instead of 10:00 turns Jan-Jun negative (-$4.0k), so it is a small, fragile adopt-candidate - default off, paper shadow first. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-losses|LIT losses]]
- Runs: `lit_u_entries_base, lit_u_entries_bstop_10, lit_u_entries_bstop_3, lit_u_entries_bstop_5, lit_u_entries_chase_any_0p25_60m, lit_u_entries_chase_any_0p4_60m, lit_u_entries_chase_any_0p6_60m, lit_u_entries_chase_exp_0p25_60m, lit_u_entries_chase_exp_0p4_120m, lit_u_entries_chase_exp_0p4_60m, lit_u_ent`
- Source: `research/writeups/lit-untested-entries.md`
- Back to [[ZEUS Home]]
