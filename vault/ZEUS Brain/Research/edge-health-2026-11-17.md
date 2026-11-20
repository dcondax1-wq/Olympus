---
tags:
  - zeus/research
  - family/other
  - verdict/research
type: "research"
date: "2026-11-17"
source: "research/writeups/edge-health-2026-11-17.md"
aliases:
  - "Edge health, 2026-11-17"
---

# Edge health, 2026-11-17

> [!abstract] Verdict: research
> (no status line)

**Full title:** Edge health, 2026-11-17: is the market still the 2026 kind?

## Summary

1. Export the missing bars: in TradingView open `CME_MINI:NQ1!` at 1 minute (all hours, B-ADJ off), Export chart data from Oct 16 to today, save it in `data/tv_exports/`, then run `python data/import_futures.py csv NQ data/tv_exports/<file>.csv` (do the same for 5 minutes and `CME_MINI:ES1!` 5 minutes). Or simply start the PC bot: its heartbeat pushes the NinjaTrader bars and this check reads them. 2. Rerun: `python tools/edge_health.py --fetch` (then `python tools/biz_publish.py --fixture` to refresh the Business card). 3. Buy rule of thumb: GREEN = fine to buy; AMBER = wait for the next payout; RED = do not buy, the edge looks like 2021-25 (about $0).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-17]]
- Refers to: [[drift-switch-2026-11-17|"Edge stopped working" switch]]
- Source: `research/writeups/edge-health-2026-11-17.md`
- Back to [[ZEUS Home]]
