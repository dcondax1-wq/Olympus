---
tags:
  - zeus/research
  - family/kalshi
  - verdict/research
  - bot/kalshi
type: "research"
date: "2026-11-21"
status: "one real hole found and fixed (a bet could be forgotten); the edge still looks real at $2.50 but only in-sample; current setting OK; gold-only offered as a Decide card"
source: "research/writeups/kalshi-k8-live-2026-11-21.md"
aliases:
  - "K8 goes live Monday"
---

# K8 goes live Monday

> [!abstract] Verdict: research
> one real hole found and fixed (a bet could be forgotten); the edge still looks real at $2.50 but only in-sample; current setting OK; gold-only offered as a Decide card

**Full title:** K8 goes live Monday (2026-11-23, $55, $2.50 a bet): red team of the live path + the edge at your size

## Summary

- **Safe:** one real hole, now fixed. If Kalshi took an order but its answer got lost (a timeout, a Kalshi 502, or the PC dying in the middle of the send), the bot **forgot the bet**. That bet wasn't counted by the day / week / peak stops, and a restart in the same 45 seconds could buy the same market **twice**. Now every bet is saved *before* it is sent. An unclear answer keeps it as "check": counted as already lost by every stop, and blocking a second bet on that market. After the result it is booked from Kalshi's own fills. Everything else held: key, phrase, sizes, stops, the price cap, settlement, errors. - **Money:** at $2.50 a bet on the 3 live legs, the history says about **+$12 a week**. If the real edge is 10 points weaker (the planning case), about **+$6 a week**. No simulated run fell below $30. This is still the friend's own months. Only 6 bets are new since Nov 18 (3 won, ...

## Links

- Family: [[Family kalshi]]
- Day: [[Day 2026-11-21]]
- Strategies: [[Kalshi K8]]
- Source: `research/writeups/kalshi-k8-live-2026-11-21.md`
- Back to [[ZEUS Home]]
