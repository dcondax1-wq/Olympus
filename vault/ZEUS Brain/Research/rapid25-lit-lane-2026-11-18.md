---
tags:
  - zeus/research
  - family/risk
  - verdict/research
  - bot/zlarior
  - lane/rapid
type: "research"
date: "2026-11-18"
status: "done - paper only. Rule (b) \"1 micro, bank at the day's room\" is a small win on speed and payout in both 2026 halves; built OFF in engine/rapid.py + engine/multi_account.py; owner yes/no. Nothing ..."
source: "research/writeups/rapid25-lit-lane-2026-11-18.md"
aliases:
  - "Rapid EOD 25K"
---

# Rapid EOD 25K

> [!abstract] Verdict: research
> done - paper only. Rule (b) "1 micro, bank at the day's room" is a small win on speed and payout in both 2026 halves; built OFF in engine/rapid.py + engine/multi_account.py; owner yes/no. Nothing live changed.

**Full title:** Rapid EOD 25K - which LIT lane rule under the 30% best-day rule

## Summary

On the Rapid EOD 25K eval, today's guard skips 65% (Jan-Jun) / 60% (Jul-Oct) of LIT trades because 1 micro's winner pays more than the day's $427 room. (b) taking those at 1 micro with the exit limit at the room passes in 28 / 20 sessions vs 31 / 25, first payout 45 / 44 vs 48 / 50 sessions from buying, $2,317 / $1,038 vs $2,312 / $972 a month; costs 60-session fails 1.3 / 1.4% vs 0.3 / 0.7% (2-week fails 0% either way). (c) letting the day break 30% and (d) LIT off are both clearly worse.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-18]]
- Strategies: [[Zlarior (LIT)]], [[Rapid lanes]]
- Runs: `none (research/lab/rapid25_lit_lane.json)`
- Source: `research/writeups/rapid25-lit-lane-2026-11-18.md`
- Back to [[ZEUS Home]]
