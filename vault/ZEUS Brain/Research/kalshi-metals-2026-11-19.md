---
tags:
  - zeus/research
  - family/kalshi
  - verdict/research
  - bot/kalshi
type: "research"
date: "2026-11-19"
status: "real clock pattern on 3.5 months of Kalshi data, positive in both halves; PAPER candidate only (research/lab/kalshi_candidates/K8.json); nothing armed"
source: "research/writeups/kalshi-metals-2026-11-19.md"
aliases:
  - "Kalshi K8 commodities"
---

# Kalshi K8 commodities

> [!abstract] Verdict: research
> real clock pattern on 3.5 months of Kalshi data, positive in both halves; PAPER candidate only (research/lab/kalshi_candidates/K8.json); nothing armed

**Full title:** Kalshi K8 commodities - the friend's "printer" bot (15-minute gold/silver clock bets + index-roll bets)

## Summary

**What his bot does.** Kalshi has "will gold be up in the next 15 minutes?" markets (also silver, natural gas, oil). Each one lives exactly 15 minutes. His bot buys one side **20 seconds after a market opens**, at fixed clock times, every weekday: - **05:15 -> 05:30 ET: gold and silver DOWN.** The quarter hour before London's gold auction (10:30 London). - **16:45 -> 17:00 ET: gold and silver UP.** The last quarter hour before the CME futures close (17:00 ET). - Sometimes **16:00 -> 16:15 ET: silver DOWN.** - **"Roll" tickets**, 5 days a month: natural gas UP (Brent DOWN), 2-3 contracts at 48-95c. On the 5th-9th business day of each month, the natural-gas and oil prices Kalshi settles on (Pyth) move to next month's futures, one slice a day at 17:00 ET. Natural gas jumped +0.6% to +2.7% in that quarter hour on all 15 such days we have.

## Links

- Family: [[Family kalshi]]
- Day: [[Day 2026-11-19]]
- Strategies: [[Kalshi K8]]
- Source: `research/writeups/kalshi-metals-2026-11-19.md`
- Back to [[ZEUS Home]]
