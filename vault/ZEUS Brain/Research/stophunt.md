---
tags:
  - zeus/research
  - family/other
  - verdict/promising
  - bot/atlas
type: "research"
date: "2026-10-23"
status: "promising"
source: "research/writeups/stophunt.md"
aliases:
  - "STOP-HUNT family"
---

# STOP-HUNT family

> [!tip] Verdict: promising
> promising

**Full title:** STOP-HUNT family - retail stop pools, the hunt, a resweep or inducement, then a strong candle toward the draw

## Summary

Owner (2026-10-23) - retail stops sit at obvious highs and lows; wait for them to be hunted, a resweep or an inducement, then a strong candle toward the draw on liquidity, with LIT's 55% win rate or better. Built as its own strategy, any hour 24/5 - 16 retail pool types (1m/5m/15m/1h swings, equal highs/lows, range edges, 3-touch trendlines, Asia/London/NY/overnight/day/week highs and lows, round numbers) ranked by obviousness, 9 hunt variants (immediate reclaim, resweep of the pool, double hunt of the new extreme, inducement before or after the hunt), displacement triggers, DOL targets from the live pool map. 28.7 million variants on CME NQ1! (costs $1.90 a micro + 1 tick, $500 risk a trade, no look-ahead, checked on data cut at each signal). The honest headline - on average a stop-hunt reversal is worth nothing (about 0 R before costs, win 46-49%), and a period's result says nothing about another period (t-stat correlation H1 vs H2 -0.003). Picking on 2026 H1 alone, as asked, fails - the H1 winners (80% win rate) lose in 2021-24 and are positive in H2 no more often than chance. Picking on H1 + 2025 + 2021-24 with H2 untouched finds two leads, both with a win rate of 55% or more in every period. (1) Asia resweep hunt (18:00-02:00, 15m/1h/session pools, re-run, 1.2 ATR candle beyond the last swing, 2R) - H1 +$8.1k (71% win, PF 2.60), H2 +$2.9k (58%, PF 1.37), 2025 +$11.0k, 2021-24 +$22.7k, about 2 trades a week; random-time placebo p 0.000 over all periods but 0.25 in H2 alone; this region of settings beats chance as a family. (2) Trend inducement hunt (5m swings, inducement first, pullback against the 1h trend, 1.2 ATR MSS candle, limit at mid-candle, 2R) - H1 +$6.5k (66%), H2 +$4.9k (67%, PF 2.30, random-time p 0.03), 2025 +$13.4k, 2021-24 +$26.3k; but its family does not beat chance. Best use - members of ATLAS on the Builder 25K (account B) - 2-week pass rises in all four periods (H1 68.9 to 74.8-79.8%, H2 43.5 to 56.5-65.2%, 0 fails). On their own account they pass too slowly; next to LIT on the 50K the trend hunt adds H2 money, the Asia hunt adds eval fails. Paper only.

## Money first

- **Honest answer to "find gold":** the hunt of retail stops is not an edge by itself - price runs through obvious stops
  all the time and reverses only about half of the time. Two narrower setups hold up across 5 years with a 55%+ win rate and
  PF 1.27-2.6: the **Asia resweep hunt** (strongest evidence as a family) and the **trend inducement hunt** (best untouched H2,
  weaker family evidence). They make about +$600-1,300 a month each at $500 risk, much less than LIT in 2026, but unlike LIT
  they also made money in 2021-24.
- **Recommendation:** paper-log both as ATLAS members on account B (Builder 25K), next to EMA / MACD / S/R. Nothing is wired
  into the bot; `live_model*.json`, `second_model.json`, `engine/lit.py` and `engine/live.py` are untouched. If the owner wants
  them on paper, the next job is a `second_model.json` plugin (`live_run`) around `engine/stophunt.py` + a live parity test.
- Not for the LIT 50K eval (the Asia hunt adds fails; LIT stays alone).

## Links

- Family: [[Family other]]
- Day: [[Day 2026-10-23]]
- Strategies: [[ATLAS]]
- Refers to: [[atlas-confluences|ATLAS]], [[lit-all-hours|LIT all hours]], [[lit-more-entries|LIT more entries]], [[lit-retail-entries|LIT retail entries]], [[retail-standalone|Retail strategies on their own]], [[second-sr|A second strategy next to LIT]], [[stophunt-audit|STOP-HUNT audit]]
- Runs: `sh_asia_resweep, sh_trend_idm5, sh_trend_idm, sh_book, sh_atlas25k_asia, sh_atlas25k_book, sh_withlit50k_trend5, sh_h1pick_asia, sh_h1pick_trend`
- Source: `research/writeups/stophunt.md`
- Back to [[ZEUS Home]]
