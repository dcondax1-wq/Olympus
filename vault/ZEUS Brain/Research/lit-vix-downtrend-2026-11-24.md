---
tags:
  - zeus/research
  - family/other
  - verdict/research
  - bot/zlarior
type: "research"
date: "2026-11-24"
source: "research/writeups/lit-vix-downtrend-2026-11-24.md"
aliases:
  - "LIT in high-VIX falling markets"
---

# LIT in high-VIX falling markets

> [!abstract] Verdict: research
> (no status line)

**Full title:** LIT in high-VIX falling markets: bad luck or a losing regime? (2026-11-24)

## Summary

Lead's question after the live audit: LIT had 0 real winners in its 7 twin trades Oct 19 - Nov 20 while NQ fell 31k -> 25k. PAPER RESEARCH ONLY. Rules written first: `research/litvix/DESIGN.md`. Code `research/litvix/study.py` -> `results.json`. Trades: the live LIT rules 2021-10 .. 2026-10-16 (run lit_live, 631) + the twin on PC bars to Nov 20 (7), risk-matched $, costs in.

## Money first

- **The premise was off: the losers did NOT come at VIX 25+.** At the 7 live-window entries the prior VIX close was 17.5-21.2
  (6 in 15-20, 1 in 20-25). VIX only went 25+ around Nov 20, after the trades. 6 of 7 had a 20-day DOWN trend.
- **VIX 25+ is LIT's BEST band**: 2021-25 70 trades, win 67%, PF 2.50, +$9,590; Jan-Jun 2026 6 trades, PF 22.7, +$4,065
  (0 in Jul-Oct). VIX 25+ with a 20-day downtrend: 2021-25 PF 2.66 (longs PF 1.74, shorts 4.43).
- **0 real winners in 7 is normal for LIT.** Real winners (+0.5R or more) are about 1 trade in 5-6 (2021-25 14%,
  Jan-Jun 23%, Jul-Oct 33%; the rest are breakeven scratches and stops). Runs of 7+ trades without one: 25 in 2021-25,
  **4 in Jan-Jun 2026 (the best half ever, longest 12)**, 1 in Jul-Oct. At 2026 rates a year of trades (~125) has such a run
  99.6% of the time. On the plain "$ > 0" count the live window was W L L W L L L (longest 3; 2026 had a 7, 2021-25 a 10).

| Rule (pre-registered) | Skipped (2021-25 / H1 / H2) | 2021-25 | Jan-Jun 2026 | Jul 2026-now | Verdict |
|---|---|---|---|---|---|
| V1 longs off when VIX > 25 and the 20-day trend is down | 24 / 1 / 0 trades, those made +$1,911 / +$1,236 / $0 | +$1,265 -> -$646 | $33,901 -> $32,665, 50K eval $33,663 -> $30,575 | unchanged $9,060 | FAIL: skips winners (placebo p 0.65) |
| V2 all LIT off when VIX > 25 and the 20-day trend is down | 49 / 4 / 0, those made +$6,544 / +$3,087 / $0 | +$1,265 -> -$5,698 | $33,901 -> $30,814, eval -$7.5k | unchanged | FAIL (placebo p 0.83) |

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-24]]
- Strategies: [[Zlarior (LIT)]]
- Refers to: [[uprisk|Uprisk]]
- Source: `research/writeups/lit-vix-downtrend-2026-11-24.md`
- Back to [[ZEUS Home]]
