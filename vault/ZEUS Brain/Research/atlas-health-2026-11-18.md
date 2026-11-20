---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/atlas
type: "research"
date: "2026-11-18"
status: "nothing to switch, no Decide proposal. The 5 rule families are in the ZEUS Lab as kind atlas_funded (all Rejected). second_model.json, data/account_b.json, live_model*.json and every engine file ..."
source: "research/writeups/atlas-health-2026-11-18.md"
aliases:
  - "ATLAS health"
---

# ATLAS health

> [!failure] Verdict: rejected
> nothing to switch, no Decide proposal. The 5 rule families are in the ZEUS Lab as kind atlas_funded (all Rejected). second_model.json, data/account_b.json, live_model*.json and every engine file untouched.

**Full title:** ATLAS health (2026-11-18) - the AMBER light is a calm-market dip, not a broken member; 17 protective rules (+5 post-hoc) for the funded 25K tested, none passes; the account's real risk is getting stranded under $100 of room

## Summary

ATLAS's edge light went AMBER (its last 40 sessions to Oct 16; the card shows the old eval-sized $ PF 1.41 vs a 2026 median 2.86). At a fixed size those 40 sessions were still +8.0R (PF 1.89, 3 trades a week) and the equity was only 1R under its high - ATLAS made less, it did not lose. No member is broken (S/R made the least: +0.3R on 7 trades; no member's own last 10 or 20 trades are under PF 1). The cause is the calmest market of the year: every session Aug 24 - Oct 16 had a prior VIX close under 18 (Jan-Jun: 54% were 18+) and NQ's RTH range was 1.05% (Jan-Jun 1.46%), so ATLAS's VIX-band targets shrank. Such a dip is normal for 2026 (26% of Jan-Jun's 40-session windows were as weak; Jan-Feb 2026 was worse and came back to PF 3+ by March) but would be a GOOD stretch by ATLAS's 2021-25 standard (median PF 1.0-1.2). Since Oct 19 the calm has ended (VIX 17-28, RTH range 1.74%) and the PC's paper trades to Nov 6 made +8.6R on 11 trades: with them the light would read GREEN. 17 pre-declared protective rules + 5 post-hoc neighbours on the funded 25K Monte Carlo (MFFU Builder 25K funded rules, 600 paths, from a fresh start and from today's -$113, real day order, fixed $250 view, random-timing controls): none passes. Day loss caps, skips and light-based sizes cost $18-191 a month in a Jul-Oct market or slow the first payout; the member pause passes the money / safety gate only because it never acts in Jul-Oct (Jul-Oct cannot check it). Found on the way: the live bot stops ATLAS for good once the funded room is under $100, and at today's 60%-of-the-room size that strands about 1 funded 25K in 11 within 6 months in a 2026-like market (0 of 42 on the real 2026 day order) and about 19 in 20 in a 2021-25-like market; the older funded tools showed 0% lost because they let it keep trading 1 micro. Risking 40% of the room halves the 2026 stranding at the same $ a month but the first payout comes 2-6 sessions later, so it fails the speed test.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-18]]
- Strategies: [[ATLAS]]
- Runs: `none (research/second/atlas_health.json, atlas_health_diag.json; tools/atlas_health.py)`
- Source: `research/writeups/atlas-health-2026-11-18.md`
- Back to [[ZEUS Home]]
