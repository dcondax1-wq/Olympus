---
tags:
  - zeus/research
  - family/other
  - verdict/info
type: "research"
date: "2026-10-17"
status: "info"
source: "research/writeups/stress-tests.md"
aliases:
  - "Stress tests of the locked strategy"
---

# Stress tests of the locked strategy

> [!note] Verdict: info
> info

**Full title:** Stress tests of the locked strategy: costs, price feed, worst start, size rounding, contract caps, late fills

## Summary

The locked strategy survives 2-tick slippage or doubled commission (2021-25 still +$13-14k, PF 1.21-1.22) but 3 ticks plus doubled commission takes 58% of its 2021-25 profit (+$6.9k, PF 1.11), and about half of every cost hit comes from the cold-streak filter flipping state on 3-26 trades. TradingView (MNQ1!) and the Python bot (NQ1!) will end a year roughly $5k apart with no bias; the fastest way to fail an eval is 7-8 full-size losers right after a good run (6-8 sessions, Feb 2023 and Nov 2024); 47% of trades are 1 micro and cost about $450 a year; a 20-micro cap costs 17% of the profit, a 10-micro cap 39%; filling one bar late loses about half of 2021-25.

## Money first

1. Costs: fine at 2 ticks or double commission; 3 ticks plus double commission takes 58% of 2021-25 and most of its
   eval odds. Half of any cost hit arrives through the cold-streak filter flipping state, which is a knife-edge at 0R.
2. TradingView and the Python bot will disagree on about 1 trade in 6 and end a year a few thousand dollars apart
   (about $5k either way), with no bias. Do not "fix" that; judge the live record with that tolerance.
3. The way to lose an eval fast is 7-8 full-size losers right after a good run (6-8 sessions, happened in Feb 2023
   and Nov 2024). The filter cannot stop that: it needs 15 signals to turn.
4. 47% of trades are 1 micro, they lose about $450 a year, and that is the price of the cold-streak mechanism.
   Rounding down costs another $440 a year; nothing to do about either.
5. The 40-micro cap matters: 3% of trades make 17% of the money.

None of this changes the lock. No adopt candidates.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-17]]
- Refers to: [[monte-carlo-evals|Monte Carlo of the MFFU 50K eval]]
- Runs: `stress_slip2, stress_slip3, stress_comm2, stress_slip2_comm2, stress_slip3_comm2, stress_max20, stress_max10, stress_skip_1micro, stress_late1bar_approx`
- Source: `research/writeups/stress-tests.md`
- Back to [[ZEUS Home]]
