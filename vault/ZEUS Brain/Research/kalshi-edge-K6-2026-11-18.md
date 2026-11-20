---
tags:
  - zeus/research
  - family/kalshi
  - verdict/rejected
  - bot/kalshi
type: "research"
date: "2026-11-19"
status: "rejected - no edge proven (Fed vs bill-implied, Treasury yields vs official par yields + vol model, daily SOFR); no candidate file written"
source: "research/writeups/kalshi-edge-K6-2026-11-18.md"
aliases:
  - "Kalshi edge, team K6"
---

# Kalshi edge, team K6

> [!failure] Verdict: rejected
> rejected - no edge proven (Fed vs bill-implied, Treasury yields vs official par yields + vol model, daily SOFR); no candidate file written

**Full title:** Kalshi edge, team K6 (Fed, Treasury yields, SOFR vs official rates data): NO EDGE PROVEN

## Summary

Research only. Kalshi's PUBLIC market data (GET, no key, at most 1 request a second, never an order) and free official data: Treasury par / constant-maturity yields, T-bill yields, the Fed target range, EFFR, SOFR and Freddie Mac PMMS, all from FRED's public csv download (the Treasury yields there are Treasury's own daily par curve: checked against 6,728 Kalshi settlement values, 0 mismatches). Nothing armed, no key used, the live bot untouched.

## Links

- Family: [[Family kalshi]]
- Day: [[Day 2026-11-19]]
- Strategies: [[Kalshi K8]]
- Source: `research/writeups/kalshi-edge-K6-2026-11-18.md`
- Back to [[ZEUS Home]]
