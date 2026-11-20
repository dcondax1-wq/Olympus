---
tags:
  - zeus/research
  - family/other
  - verdict/adopt-candidate
type: "research"
date: "2026-10-26"
status: "adopt-candidate (owner decides; built, OFF) - decide on an NQ chart (signal_root NQ), keep every order on MNQ"
source: "research/writeups/mnq-vs-nq-feed.md"
aliases:
  - "MNQ feed vs NQ backtest"
---

# MNQ feed vs NQ backtest

> [!success] Verdict: adopt-candidate
> adopt-candidate (owner decides; built, OFF) - decide on an NQ chart (signal_root NQ), keep every order on MNQ

**Full title:** MNQ feed vs NQ backtest - does the bot trade the backtest's signals? (and the NQ signal chart option)

## Summary

LIT is backtested on NQ1!, the PC decides on NinjaTrader MNQ. The PC's MNQ bars (27 heartbeat commits) equal TradingView MNQ1! on 95% of bars but are within a tick of NQ1! on only 54-62%. On 40 sessions (Aug 24 - Oct 16, 5m execution) 36% of LIT's setups exist on one feed only, 60% of trade days differ, NQ +$2,362 vs MNQ +$367. On the whole of 2026 with MNQ-sized noise (40 draws, 1m execution) the median is $32.8k vs $43.8k, H2 $9.1k vs $9.9k (-$229 a month; -$460 with the noise negated), only ~28% of trades identical; a vendor-noise control changes nothing. Built OFF - signal_root NQ reads an NQ chart's LE_BarFeed files for every decision, orders / stops / targets / size stay MNQ. Paper only; nothing live changed.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-26]]
- Runs: `lit_feed_mnq_noise, lit_feed_mnq_live_5m, lit_feed_nq_same_5m`
- Source: `research/writeups/mnq-vs-nq-feed.md`
- Back to [[ZEUS Home]]
