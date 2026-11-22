---
tags:
  - zeus/research
  - family/other
  - verdict/info
  - bot/zlarior
type: "research"
date: "2026-10-18"
status: "info"
source: "research/writeups/lit-live-fills.md"
aliases:
  - "LIT live fills"
---

# LIT live fills

> [!note] Verdict: info
> info

**Full title:** LIT live fills - how the orders really fill on the MFFU account, and what that does to the numbers

## Summary

A study of how LIT's orders fill on NinjaTrader -> Tradovate -> CME for the MFFU account, and a realistic fill model built from it (engine/lit.py option "fills", off by default). No backtest matches live exactly, so this is the most realistic model we can defend, plus a tool (tools/fill_audit.py) that measures the real fills. Order handling costs little. MFFU's $1.90 commission, stop slippage, the spread, the tick-rounded target limit and the breakeven lag together cost about $1.2k of 2026's $41.7k under the LIT size rule (+$40.5k, PF 3.48 instead of 3.66). H2 is unchanged at about $2,400-2,500 a month. The real problem is timing. The PC bot sees the entry only after the 1m bar after the CISD has closed, then waits for its next 60-second poll, so it buys about 95 s late. The entry lands anywhere from 9 points better to 25 points worse (sd 7.5 pts) and can risk up to 1.65 times the planned amount. On the eval sizing the bots trade, that drops the 2026 pass rate from 85% to 71% and 1-month passes from 55% to 50%. With two small code fixes (decide on the CISD bar's close, poll 2 s after each minute) the entry is 6 s late, the error is 0.6 pts and the eval odds are back to the backtest's (pass rate 85%, 2 weeks 34.5% / 2.4%). Keep stop-market stops and the target where it is. Paper only.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-18]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[lit-report-coverage|LIT report coverage]]
- Runs: `lit_fill_live_today, lit_fill_live_today_eval, lit_fill_live_fixed, lit_fill_live_fixed_eval, lit_fill_stress, lit_fill_stress_eval, lit_fill_n0, lit_fill_s1_comm, lit_fill_s2_target, lit_fill_s3_stops, lit_fill_s4_spread, lit_fill_inside1, lit_fill_fixed_in1`
- Source: `research/writeups/lit-live-fills.md`
- Back to [[ZEUS Home]]
