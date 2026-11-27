---
tags:
  - zeus/research
  - family/money
  - verdict/research
type: "research"
date: "2026-11-26"
status: "research + a READ-ONLY planner. No live change: the bot already asks at the max. Nothing requests a payout."
source: "research/writeups/payout-year-2026-11-26.md"
aliases:
  - "Payout engine + 12-month request policy"
---

# Payout engine + 12-month request policy

> [!abstract] Verdict: research
> research + a READ-ONLY planner. No live change: the bot already asks at the max. Nothing requests a payout.

**Full title:** Payout engine + 12-month request policy - ask for the full max each time; when you ask moves < $25 a year, the market moves thousands

## Summary

**Plain answer:** the request habit the bot already uses (ask for the full max once it sits above the buffer, payouts 1-4, never #5) is the best or tied in every account. Asking earlier gets the first payout ~3-6 trading days sooner but less cash in total. What decides the money is whether the market stays 2026-like (about $3,000 a year from the 25K, $6,000 from the 50K) or goes back to 2021-25 (a few hundred, and the account is usually lost within the year).

## Links

- Family: [[Family money]]
- Day: [[Day 2026-11-26]]
- Runs: `tools/money/payout_year.py -> research/payout/results.json (design research/payout/DESIGN.md 700b7705e + erratum 073e031ed, before the run); engine/payout_engine.py (planner, /today, Money tile)`
- Source: `research/writeups/payout-year-2026-11-26.md`
- Back to [[ZEUS Home]]
