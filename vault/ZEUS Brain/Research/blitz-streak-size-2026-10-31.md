---
tags:
  - zeus/research
  - family/risk
  - verdict/rejected
  - bot/blitz
type: "research"
date: "2026-10-31"
status: "rejected (no change, no switch) - the H1 pick, half size on the trade after a same-day BLITZ loss, adds $0 / +$1 / -$1 a month to the slot (H1 / H2 / 2021-25) and loses to shuffled outcomes in 2021-25"
source: "research/writeups/blitz-streak-size-2026-10-31.md"
aliases:
  - "BLITZ in-day streak size"
---

# BLITZ in-day streak size

> [!failure] Verdict: rejected
> rejected (no change, no switch) - the H1 pick, half size on the trade after a same-day BLITZ loss, adds $0 / +$1 / -$1 a month to the slot (H1 / H2 / 2021-25) and loses to shuffled outcomes in 2021-25

**Full title:** BLITZ in-day streak size (2026-10-31 evening) - size the day's next BLITZ trade by how its previous one ended

## Summary

Eval size of the day's next BLITZ trade by the previous one's result (x m_loss after a same-day loss, x m_win after a win, on top of the later-break size; 7 cells, pick on 2026 H1, 1,000 Monte Carlo paths, 10 shuffled-outcome controls). H1 pick x0.5 after a loss: slot $286 / $53 / -$40 a month (today $286 / $52 / -$39), 2-week pass/fail 50.4/21.8 vs 47.9/23.5 (H1), 40.6/17.4 vs 36.2/21.7 (H2), 23.1/47.7 vs 24.7/48.4 (2021-25); $150 view $1,179 / $1,170 / $20 a month vs $1,413 / $1,228 / $124, PF 1.78 / 2.08 / 1.01 vs 1.74 / 1.88 / 1.05. Trades after a loss average +0.14R / +0.08R / +0.07R (H1 / H2 / 2021-25), after a win +0.22R / +0.31R / -0.02R: the sign flips in 2021-25. Rejected.

## Money first

**Nothing changes.** Sizing BLITZ's next trade by how the day's previous one ended does not make you money. The H1 pick
(half size on the trade after a same-day loss) leaves the 25K slot where it is: **$286 / $53 / -$40 a month** (2026 H1 /
H2 / 2021-25), against **$286 / $52 / -$39** for today's size. In 2021-25 it is worse than the same size on shuffled
outcomes. No switch was added; account C trades exactly as before.

| Set-up (eval size; funded unchanged) | Slot $ a month to you, net of $63 evals: H1 / H2 / 2021-25 | 2-week pass / fail H1 / H2 / 2021-25 | $150 a trade: $ a month, PF, max DD (H1 / H2 / 2021-25) | Trades a week |
|---|---|---|---|---|
| Today (later-break size on) | $286 / $52 / -$39 | 47.9/23.5 · 36.2/21.7 · 24.7/48.4 | $1,413 / $1,228 / $124 · PF 1.74 / 1.88 / 1.05 · DD -$1,184 / -$1,253 / -$8,926 | 8.5 / 6.8 / 8.6 |
| **H1 pick: x0.5 after a same-day loss** | **$286 / $53 / -$40** | 50.4/21.8 · 40.6/17.4 · 23.1/47.7 | $1,179 / $1,170 / $20 · PF 1.78 / 2.08 / 1.01 · DD -$1,172 / -$1,133 / -$8,435 | 8.5 / 6.8 / 8.6 |
| Same x0.5 on shuffled outcomes (10 seeds) | $277 / $47 / -$39 | 43.8/25.5 · 34.8/20.6 · 22.6/43.6 | net $7,027 / $3,668 / $4,333 (whole span) | same |
| Skip the trade after a loss (x0) | $274 / $53 / -$41 | 42.9/27.7 · 42.0/8.7 · 20.1/42.1 | $944 / $1,113 / -$85 · PF 1.85 / 2.45 / 0.95 | 5.9 / 4.8 / 5.7 |
| x1.5 after a win | $289 / $52 / -$39 | 48.7/26.1 · 36.2/21.7 · 25.6/49.8 | $1,845 / $1,744 / $85 · PF 1.78 / 2.03 / 1.03 · DD -$1,626 / -$1,736 / -$12,671 | 8.5 / 6.8 / 8.6 |
| x1.5 after a loss | $286 / $52 / -$39 | 47.1/23.5 · 36.2/21.7 · 25.0/49.2 | $1,648 / $1,285 / $228 · PF 1.71 / 1.75 / 1.07 | 8.5 / 6.8 / 8.6 |
| x0.5 after a win | $258 / $40 / -$40 | 36.1/31.9 · 27.5/20.3 · 19.5/39.1 | $981 / $711 / $163 · PF 1.67 / 1.65 / 1.08 | 8.5 / 6.8 / 8.6 |

**Why it fails.** The trade after a same-day loss is not a worse trade everywhere. Average R, costs in:

| | 2026 H1 | 2026 H2 | 2021-25 |
|---|---|---|---|
| Day's first BLITZ trade | +0.10R (60) | +0.14R (28) | -0.01R (502) |
| After a same-day loss | +0.14R (66) | +0.08R (31) | **+0.07R** (610) |
| After a same-day win | +0.22R (91) | +0.31R (47) | -0.02R (729) |

In 2026 the trade after a win is the best one. In five years of 5m bars it is the worst, and the trade after a loss is the
best. The H2 gain of the pick (fail in 2 weeks 17.4% vs 21.7%) rests on 31 trades and does not hold in 2021-25.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-10-31]]
- Strategies: [[BLITZ (paper)]]
- Runs: `bzx_streak, bzx_cold`
- Source: `research/writeups/blitz-streak-size-2026-10-31.md`
- Back to [[ZEUS Home]]
