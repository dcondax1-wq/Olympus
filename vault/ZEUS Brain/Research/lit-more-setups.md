---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
  - bot/zlarior
type: "research"
date: "2026-10-19"
status: "rejected"
source: "research/writeups/lit-more-setups.md"
aliases:
  - "LIT more setups a week"
---

# LIT more setups a week

> [!failure] Verdict: rejected
> rejected

**Full title:** LIT more setups a week - ES/MES, 15m/30m/1h setups, missed fills, looser filters, higher-tier 2nd trades

## Summary

The owner said there must be more LIT setups a week. 95 variants on the exact live LIT (1m entries, live stops and VIX-band targets, Monday rule, weekly stop, $1.90 a micro), scored in $ at the LIT size and on the MFFU 50K 2-week pass rate under the live eval sizing (two_week for 10 sessions, then safe_eval), picked on Jan-Jun 2026 and checked on Jul-Oct. None passes. ES traded as MES loses money in Jan-Jun (PF 0.75, -$4.5k) and NQ+ES together fails 17-29% of evals in 2 weeks. 15m setups add 2-6 trades a half and lift the 2-week pass rate in both halves (Jan-Jun 52.9% -> 63.0%, Jul-Oct 50.7% -> 52.2%), but cost $322 in Jan-Jun and raise Jul-Oct fails 2.9% -> 7.2%. 1h setups never fit the 80-pt stop (0 trades). Re-arming missed fills, longer limits and looser filters all lose in at least one half. The extra setups exist, but they fall on days that already traded, have stops over 80 pts, or are weaker. Today's LIT stays.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-19]]
- Strategies: [[Zlarior (LIT)]]
- Runs: `lit_more_base, lit_more_es_alone, lit_more_nq_es_both, lit_more_nq_es_1day, lit_more_nq_5m_exec, lit_more_15m_add, lit_more_15m_add_best, lit_more_15m_add_2, lit_more_30m_add, lit_more_miss_retap, lit_more_miss_rearm, lit_more_miss_limit60, lit_more_miss_cisd30, lit_more_loose_disp07, lit_more_loose`
- Source: `research/writeups/lit-more-setups.md`
- Back to [[ZEUS Home]]
