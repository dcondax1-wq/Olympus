---
tags:
  - zeus/research
  - family/stops
  - verdict/rejected
type: "research"
date: "2026-10-17"
status: "rejected"
source: "research/writeups/stops.md"
aliases:
  - "Stops"
---

# Stops

> [!failure] Verdict: rejected
> rejected

**Full title:** Stops: where the stop should go

## Summary

Today's stop (2 points beyond the sweep extreme, 10-60 points) is the best of 19 variants. Wider buffers, volatility-scaled (ATR) buffers, other min/max limits and stops beyond the gap all lose money in 2026, 2021-25 or both; no stop change is recommended.

## Money first

Keep the stop exactly as it is: 2 points beyond the sweep extreme, 10-60 points, gap fallback above 60. Not one
variant beat it in both periods. The new `stop_buf_atr` option stays in the engine switched off.

## Links

- Family: [[Family stops]]
- Day: [[Day 2026-10-17]]
- Runs: `screen_baseline, stp_atr015_replay, stp_buf05, stp_buf15, stp_buf20, stp_buf30, stp_atr010, stp_atr015, stp_atr025, stp_atr050, stp_atr010_max70, stp_atr015_max70, stp_atr015_max80, stp_max45, stp_max50, stp_max70, stp_max80, stp_min8, stp_min12, stp_min15, stp_ifvg`
- Source: `research/writeups/stops.md`
- Back to [[ZEUS Home]]
