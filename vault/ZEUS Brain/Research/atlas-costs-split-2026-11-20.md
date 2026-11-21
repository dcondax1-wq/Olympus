---
tags:
  - zeus/research
  - family/second
  - verdict/info
  - bot/zlarior
  - bot/atlas
type: "research"
date: "2026-11-20"
status: "info - no change, no Decide card. tools/cost_alarm.py built (alarm only, research/lab/costs.json)."
source: "research/writeups/atlas-costs-split-2026-11-20.md"
aliases:
  - "ATLAS with split costs"
---

# ATLAS with split costs

> [!note] Verdict: info
> info - no change, no Decide card. tools/cost_alarm.py built (alarm only, research/lab/costs.json).

**Full title:** ATLAS with split costs (late entry 10 ticks, resting stop 1-3, target 0) - about +$25 a month and safer than the 10/10 stress, but no long-run edge and room 40% stays right; a nightly real-cost alarm built

## Summary

Every ATLAS study today charged the resting stop the same 10 ticks as the late market entry. Priced apart (entry 10, stop 2, target 0) on the live setup (room 40% + 2 losses -> 1 micro), from today's $1,401 room - funded 25K $539 / $459 a month (Jan-Jun / Jul-Oct-like) vs $514 / $436 at 10/10, lost in 6 months 5.4 / 3.6% vs 6.9 / 5.7%; fixed $250 view 2026 PF 2.59 / 2.24, 2025 PF 1.00, 2021-24 PF 0.89 (0.80 at 10/10) - still no long-run edge in a calm market. 25K eval 2-week pass 59.7 / 40.6% (57.1 / 39.1 at 10/10). Room 60% vs 40% at stop 1 / 2 / 3: 40% stays safer every time (no card). No real exit fill exists yet, so the stop cost is a scenario. The alarm reads NOT ENOUGH FILLS for both bots (3 ATLAS, 1 Zlarior fill); at the measured costs the last 40 sessions are PF 2.27 (ATLAS) and 3.38 (Zlarior).

## Links

- Family: [[Family second]]
- Day: [[Day 2026-11-20]]
- Strategies: [[Zlarior (LIT)]], [[ATLAS]]
- Runs: `tools/atlas_costs_split.py run -> research/second/atlas_costs_split.json; tools/cost_alarm.py -> research/lab/costs.json; design research/second/atlas_costs_split_design.md (committed before any run)`
- Source: `research/writeups/atlas-costs-split-2026-11-20.md`
- Back to [[ZEUS Home]]
