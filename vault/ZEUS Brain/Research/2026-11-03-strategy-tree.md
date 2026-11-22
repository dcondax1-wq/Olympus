---
tags:
  - zeus/research
  - family/other
  - verdict/rejected
type: "research"
date: "2026-11-03"
status: "rejected (research lens, nothing adopted) - 31 of 80 best rules hold out of sample vs 25 and 28 when the conditions are shuffled (chance level); every rule trades 0.1-0.5 times a week; the top-5 ..."
source: "research/writeups/2026-11-03-strategy-tree.md"
aliases:
  - "DAPHNE strategy-tree search"
---

# DAPHNE strategy-tree search

> [!failure] Verdict: rejected
> rejected (research lens, nothing adopted) - 31 of 80 best rules hold out of sample vs 25 and 28 when the conditions are shuffled (chance level); every rule trades 0.1-0.5 times a week; the top-5 basket makes +$29k in 2021-25 (mostly the training years) and +$541 in 2026 (PF 1.06); the #1 rule holds (2026 PF 1.33, +$95 a month) but that is what luck looks like among 80 tries

**Full title:** DAPHNE strategy-tree search (2026-11-03) - 1.13 million rule combinations on plain NQ level trades; the best rules hold out of sample no more often than shuffled noise

## Summary

The owner's TikTok "it likes moves" tree, built our own way on real CME NQ1! bars. 80 root rules (prior-day, overnight, Asia, London and opening-range highs and lows; fade after a sweep or trade the break; 1R / 2R; 60 / 120 min) grow a tree of up to 5 extra conditions each (volatility, gap, where the open sits in yesterday's range, distance from the open, hour, weekday, VWAP side, trend, VIX, opening-range width). Best-first branch-and-bound with an exact bound, trained on 2021-11 to 2024-12, tested on 2025-01 to 2026-10, with a placebo search on shuffled conditions. Page tools/web_public/tree, engine tools/strategytree.

## Money first

**Nothing changes for the bots. DAPHNE is a research lens, paper only, never routed.**

The search did what the TikTok tool does: it found rules that made a lot in the training years (+$28 to +$44 a trade
per micro, after costs). Then it met 2025-26, which it never saw. **31 of the 80 best rules still made money and beat
their plain root. With the conditions shuffled into noise, 25 and 28 of 80 did the same.** That gap is chance. The
average best rule beat its root by **+$0.61 a trade** out of sample; the two noise runs did **+$1.26** and **-$1.35**.

| What | Train 2021-24 | Test 2025-26 | 2026 alone |
|---|---:|---:|---:|
| #1 rule (AL·SHORT, 4 conditions), $ a trade per micro | +$43.70 (67 trades) | +$14.81 (45) | +$27.37 (22) |
| #1 rule at the bot's size ($282 risk a trade), run `strategytree_top1` | 2021-25: +$6,135, PF 1.54, $122/mo | 2025: -$376, PF 0.90 | +$923, PF 1.33, **$95/mo** |
| Top-5 basket at the bot's size, run `strategytree_top5` | 2021-25: +$29,056, PF 1.54, $579/mo | 2025: -$425, PF 0.97 | +$541, PF 1.06, **$55/mo** |
| Live LIT for scale (run `lit_live`) | | | +$43,820, PF 4.19 |

- **Trades a week: 0.1 to 0.5 per rule.** The owner's floor is 2-4 a week. Even the top-5 basket makes 1.7 a week in
  2026, with 2+ trades in only 48% of weeks.
- **MFFU 50K eval speed: 0% passed within 2 weeks** (2026 and 2021-25) for the #1 rule and the basket. At 0.4 trades a
  week an eval never gets decided.
- **The training years carry the money.** The basket made +$13.1k in 2022 and +$13.2k in 2024 (both in the training
  data) and lost -$425 in 2025. That is the signature of a fitted rule, not an edge.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-03]]
- Runs: `strategytree_top1, strategytree_top5`
- Source: `research/writeups/2026-11-03-strategy-tree.md`
- Back to [[ZEUS Home]]
