---
tags:
  - zeus/research
  - family/second
  - verdict/rejected
  - bot/atlas
type: "research"
date: "2026-11-20"
status: "one Decide card (atlas-funded-streak-1micro, recommend yes, open). Nothing live changed. 14 rejected (TESTED_AND_REJECTED). ES legs: no. Fresh data to Nov 19: edge holding (edge check AMBER -> GREEN)."
source: "research/writeups/atlas-edge-2026-11-20.md"
aliases:
  - "ATLAS edge at real fills"
---

# ATLAS edge at real fills

> [!failure] Verdict: rejected
> one Decide card (atlas-funded-streak-1micro, recommend yes, open). Nothing live changed. 14 rejected (TESTED_AND_REJECTED). ES legs: no. Fresh data to Nov 19: edge holding (edge check AMBER -> GREEN).

**Full title:** ATLAS edge at real fills - 1 of 15 changes passes (after 2 losses in a row, 1 micro until a win); limit orders, later entries, dropping / halving EMA and ES legs all fail

## Summary

Pre-registered (research/second/atlas_edge_design.md, commit 5b511c92, before any run), judged at 6 and 10 ticks a side on today's funded 25K ($887 room) with both today's 60% sizing and the room-40% card. Passes - E3, after 2 losing ATLAS trades in a row trade 1 micro until the next winner. At 10 ticks from today's account the chance of losing the funded 25K in 6 months goes 17.6 -> 12.2% (Jan-Jun-like) and 21.7 -> 10.9% (Jul-Oct-like) for $503 -> $481 / $402 -> $408 a month; first payout about a week later (Dec 30 / Jan 12). With room 40% as well: 10.1 / 7.7% lost, $478 / $394. Holds on a second set of random paths; neighbours (1 and 3 losses) behave monotonically. Fails - limit orders at or better than the 5m open with 1-2 minute timeouts (only ~52% of signals fill; missed winners cost $28-37k at $250 a trade over 2021-26), limit then market, the next 5m open, per-leg minutes (MACD +1 minute looks good on Jul-Oct but needs 1m bars, info only), dropping or halving EMA (the leg that loses most to slippage, but also the 2026 earner), day stop after a loss, 3-loss pause, a weekly cap. ES versions of all 3 legs lose in 2026 (PF 0.6-0.9 vs NQ 1.2-3.3).

## Money first

| Check at 10 ticks, 60% sizing | Jan-Jun-like $ / lost | Jul-Oct-like $ / lost |
|---|---|---|
| E3 on the design paths (vs today) | $481 / 12.2% ($503 / 17.6%) | $408 / 10.9% ($402 / 21.7%) |
| E3 on a second random path set (vs today on it) | $471 / 14.5% ($497 / 18.6%) | $400 / 11.7% ($389 / 23.8%) |
| Neighbour: 1 loss -> 1 micro | $457 / 10.8% | $304 / 10.9% |
| Neighbour: 3 losses -> 1 micro | $491 / 14.8% | $418 / 13.9% |

Smooth in the streak length (shorter = safer, less money), and it holds on fresh paths. Why it works where the day stop and
the pause don't: those skip trades, and ATLAS's trade after a loss is as good as any (no edge in sitting out, and MFFU's
inactivity rule punishes idling); 1 micro keeps taking the signal, so a winner still ends the streak, but a third or fourth
loss costs tens of dollars instead of a few hundred of an $887 room. It changes sizing only, so trades a week, PF and the fixed view are
the same as today.

Limits of the proof: it is a sizing rule on the Monte Carlo, the streak is updated at the end of each session (live it
would update after each trade, which can only act sooner), and 2021-25 stays a losing market for ATLAS either way.

## Links

- Family: [[Family second]]
- Day: [[Day 2026-11-20]]
- Strategies: [[ATLAS]]
- Runs: `tools/atlas_edge.py run / posthoc / es -> research/second/atlas_edge.json; tools/atlas_es.py run -> research/second/atlas_es_trades.json`
- Source: `research/writeups/atlas-edge-2026-11-20.md`
- Back to [[ZEUS Home]]
