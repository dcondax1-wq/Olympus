---
tags:
  - zeus/research
  - family/second
  - verdict/finding
  - bot/atlas
  - lane/rapid
type: "research"
date: "2026-11-20"
status: "finding - one card flips. atlas-funded-room-40 recommend no -> YES (passes the pre-registered bar at 6 and 10 ticks). atlas-funded-keep-trading stays yes. payout-ping-1000 stays no. atlas-on-rapid ..."
source: "research/writeups/atlas-risk-real-fills-2026-11-20.md"
aliases:
  - "ATLAS funded 25K at real fills"
---

# ATLAS funded 25K at real fills

> [!info] Verdict: finding
> finding - one card flips. atlas-funded-room-40 recommend no -> YES (passes the pre-registered bar at 6 and 10 ticks). atlas-funded-keep-trading stays yes. payout-ping-1000 stays no. atlas-on-rapid stays yes. Pause / stop: no. Nothing live changed.

**Full title:** ATLAS funded 25K at real fills - room 40% now wins, keep trading (don't pause), $750 ping and the Rapid ATLAS lane stay

## Summary

At 10 ticks a side (ATLAS's real fills) the funded 25K from today's $887 room makes $503 / $402 / $19 a month (Jan-Jun / Jul-Oct / 2021-25-like) and is lost in 6 months 17.6 / 21.7 / 98.8% of the time. Risking 40% of the room instead of 60% gives $527 / $393 / $16 and 11.0 / 14.0 / 98.2% lost, first payout 3-8 trading days later: it passes the bar. The owner's keep-trading YES is right (the old $100 stop loses 20.3 / 23.5%). Asking at $1,000 passes narrowly on its own (16.0 / 20.7%) but adds under 1 point once room 40% is in and pays later. A 4-week pause costs $34-55 a month and is no safer; stopping is $0. Trading 1 micro for 5 weeks also passes (12.7 / 18.9%). Rapid 25K: ATLAS $250 still adds $609-1,662 a month at 10 ticks.

## Links

- Family: [[Family second]]
- Day: [[Day 2026-11-20]]
- Strategies: [[ATLAS]], [[Rapid lanes]]
- Refers to: [[atlas-fills-2026-11-20|ATLAS real fills]]
- Runs: `tools/atlas_risk.py run / posthoc -> research/second/atlas_risk.json; design research/second/atlas_risk_design.md (committed e4e63c97 before any run)`
- Source: `research/writeups/atlas-risk-real-fills-2026-11-20.md`
- Back to [[ZEUS Home]]
