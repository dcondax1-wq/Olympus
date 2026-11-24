---
tags:
  - zeus/research
  - family/stops
  - verdict/rejected
type: "research"
date: "2026-11-24"
status: "rejected"
source: "research/writeups/stops-targets-time-2026-11-24.md"
aliases:
  - "\"Stops x targets x TIME"
---

# "Stops x targets x TIME

> [!failure] Verdict: rejected
> rejected

**Full title:** "Stops x targets x TIME: smaller stops and take-profits from other timeframes, and TIME x PRICE"

## Summary

"19 pre-registered variants on the exact live LIT trades (631, 120 in 2026, 1m fills). Tighter stops from the 1m CISD candle, the 1m entry swing and the 3m FVG cut the stop from ~44-52 pts to 7-22 pts, but at the same dollars at risk every one loses money in Jul-Oct ($8.3k-$14.0k less than live): 40-58% of trades get stopped and 28-41% of those stop-outs were live WINNERS (wicked out). Structure targets (15m / 1h liquidity, session highs, 1h FVG) and fixed 1.5 / 2 / 3R hit the target up to 2x as often but cut the big runners: all lose Jan-Jun by $8-25k. Time rules (N = 26 min, from Jan-Jun only) lose both halves. 0 pass; nothing changes. One lead: on the Rapid EOD 25K (30% best-day rule) a small fixed target passes evals where the band target cannot."

## Money first

- **REJECTED, all 19.** No stop, target or clock change beats live in both 2026 halves at the same $ risk; none comes near the
  Bonferroni bar (best Jul-Oct p 0.50, the 1h FVG target).
- **Keep:** stop 1 tick beyond the 5m sweep extreme, size follows the stop, the VIX band target banked at 8R, BE at +1R, the
  15-minute check.
- **Why bigger is right for LIT:** the sweep extreme is the real invalidation; anything inside it is noise that LIT's winners
  routinely trade through before running ~3 hours to the band.
- **Lead for later (Rapid lane only):** a pre-registered Rapid EOD 25K test of small fixed targets (1.5R / 2R) against the 30%
  best-day rule. Not adopted; not a LIT change.

Paper only. Nothing live changed; `live_model*.json` untouched. Re-run: `python -X utf8 tools/stops_targets_time.py all` (~1 min).

## Links

- Family: [[Family stops]]
- Day: [[Day 2026-11-24]]
- Runs: `tools/stops_targets_time.py (research/lab/stops_targets.json, research/lit/stops_time.json)`
- Source: `research/writeups/stops-targets-time-2026-11-24.md`
- Back to [[ZEUS Home]]
