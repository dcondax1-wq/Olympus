---
title: BLITZ in-day streak size (2026-10-31 evening) - size the day's next BLITZ trade by how its previous one ended
family: risk
date: 2026-10-31
status: rejected (no change, no switch) - the H1 pick, half size on the trade after a same-day BLITZ loss, adds $0 / +$1 / -$1 a month to the slot (H1 / H2 / 2021-25) and loses to shuffled outcomes in 2021-25
summary: Eval size of the day's next BLITZ trade by the previous one's result (x m_loss after a same-day loss, x m_win after a win, on top of the later-break size; 7 cells, pick on 2026 H1, 1,000 Monte Carlo paths, 10 shuffled-outcome controls). H1 pick x0.5 after a loss: slot $286 / $53 / -$40 a month (today $286 / $52 / -$39), 2-week pass/fail 50.4/21.8 vs 47.9/23.5 (H1), 40.6/17.4 vs 36.2/21.7 (H2), 23.1/47.7 vs 24.7/48.4 (2021-25); $150 view $1,179 / $1,170 / $20 a month vs $1,413 / $1,228 / $124, PF 1.78 / 2.08 / 1.01 vs 1.74 / 1.88 / 1.05. Trades after a loss average +0.14R / +0.08R / +0.07R (H1 / H2 / 2021-25), after a win +0.22R / +0.31R / -0.02R: the sign flips in 2021-25. Rejected.
runs: bzx_streak, bzx_cold
---

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

## The question

BLITZ can take up to 6 trades a day. Does the result of the day's previous BLITZ trade say how big the next one should
be? For example: half size after a loss (protect the eval), or more after a win (press when the day works). Nothing in
"Tested and rejected" or the BLITZ write-ups tested this. The closest tests were "after a winning BLITZ *day*" (the day
before, `bzx_signal_facts`: rejected) and ATLAS's "2nd trade sized by the 1st" (ATLAS only).

## How it was tested

- Today's BLITZ trades as account C, costs in. 2026 = 1m bars (H1 = Jan-Jun, H2 = Jul-Oct 16); 2021-25 = the 5m reference.
  This is the same trade set the later-break study used (`tools/bzx_edge.prep`).
- Size = today's eval size (40% of the room, at most $600, the whole room from session 5) x the later-break multiplier
  (x0.5 on a side's first break, x1.75 on a later one; ON since today) x **the new streak multiplier**:
  - x m_loss when the day's previous BLITZ trade lost;
  - x m_win when it won;
  - the day's first trade is unchanged.

  The previous trade has closed before the next entry (BLITZ holds one position), so nothing looks ahead.
- Only the eval is changed. The funded 25K keeps today's size.
- Grid: (m_loss, m_win) = (1, 1) today, (0.5, 1), (0, 1) = skip after a loss, (1, 1.5), (0.5, 1.5), (1.5, 1), (1, 0.5).
- Pick on 2026 H1: the best H1 slot $ a month whose 2-week fail rate is no worse than today's. Then check it on H2 and
  2021-25.
- Control: the picked multipliers on SHUFFLED previous-trade outcomes (10 seeds). If shuffled outcomes do as well, the
  previous result carries no information.
- Measures:
  - slot $ a month to you, net of every $63 eval (Monte Carlo, `bzx_edge.lifeX`);
  - 2-week pass / fail `p10/f10` (every start day, `bzx_edge.eval_scorex`);
  - the fixed $150-a-trade view: net $, $ a month, PF in $, max drawdown, trades a week, average R.

Tool: `python -X utf8 tools/bzx_streak.py` -> `research/scalp/bzx_streak.json` + run `bzx_streak`.

## Results

- **Pick (H1 only, written before looking at H2):** the cell with the best H1 slot $ a month among those whose H1 2-week
  fail rate is no worse than today's. x0.5 after a loss and x1.5 after a loss tie at $286; the rule takes the first,
  x0.5 / x1.
- **H2 check:** slot +$1 a month ($53 vs $52), pass/fail in 2 weeks 40.6/17.4 vs 36.2/21.7. Better than shuffled outcomes
  ($47, 34.8/20.6).
- **2021-25 check:** slot -$1 a month (-$40 vs -$39). Pass in 2 weeks falls 1.6 points and fail falls 0.7 (23.1/47.7 vs
  24.7/48.4). The $150 view drops from $124 to $20 a month (PF 1.05 -> 1.01). Shuffled outcomes do as well on the slot
  (-$39) and better on fail (43.6%).
- **Trades a week** are unchanged (8.5 / 6.8 / 8.6) for every cell except skip-after-a-loss (5.9 / 4.8 / 5.7). All cells
  keep 2+ a week.
- **Most multipliers move the slot by $3 a month or less.** Two cells are worse: skip after a loss (-$12 in H1) and x0.5
  after a win (-$28 / -$12 in H1 / H2). The eval slot is decided by the room / target / stuck rules, not by this.
- Data: `research/scalp/bzx_streak.json` (grid, facts, control seeds). Run `bzx_streak`: stored trades at $150 x
  later-break x the pick's multiplier.

## Verdict

**Rejected.** It does not hold in 2021-25 (slot -$1 a month, the $150 view $124 -> $20, no better than shuffled outcomes),
and in 2026 it adds nothing to the money ($0 / +$1 a month). Do not retry in-day streak sizing for BLITZ without a new
fact that separates good from bad trades after a loss. The same-day sequence by itself is noise across the 5 years.

Nothing is adopted. BLITZ's trades and account C's size stay exactly as they are; no switch was added.

## Follow-up (19:40): cold-streak size on BLITZ's own last trades - rejected

**Money first.** This also changes nothing. The H1 pick (half size while BLITZ's last 5 trades sum below 0R) gives a slot
of **$288 / $52 / -$40 a month** (H1 / H2 / 2021-25), against **$286 / $52 / -$39** today. Shuffled cold / warm flags
give $279 / $48 / **-$37**, so in 2021-25 the rule does worse than chance.

- **The rule:** the eval size goes x m_cold when the sum of R of BLITZ's previous K trades is below 0, else x m_warm. It
  runs on top of the later-break size; the funded size is unchanged. Those K trades closed before the entry, so nothing
  looks ahead.
- **Grid:** K = 5 / 10 / 20; (m_cold, m_warm) = (0.5, 1), (1.5, 1), (1, 1.5). Same gate and harness as above (1,000 paths,
  10 shuffled controls). Tool: `tools/bzx_cold.py`, run `bzx_cold`, data `research/scalp/bzx_cold.json`.
- **This is new:** the cross-day version of the streak idea. It is not LIT's cold-streak filter, and not ATLAS's member
  weights.

| | Slot $ a month H1 / H2 / 2021-25 | 2-week pass / fail H1 · H2 · 2021-25 | $150 a trade: $ a month, PF, max DD | Trades a week |
|---|---|---|---|---|
| Today | $286 / $52 / -$39 | 47.9/23.5 · 36.2/21.7 · 24.7/48.4 | $1,413 / $1,228 / $124 · PF 1.74 / 1.88 / 1.05 · DD -$1,184 / -$1,253 / -$8,926 | 8.5 / 6.8 / 8.6 |
| **H1 pick: K 5, x0.5 when cold** | **$288 / $52 / -$40** | 47.1/23.5 · 40.6/17.4 · 23.3/44.3 | $1,182 / $1,112 / $8 · PF 1.76 / 1.99 / 1.00 · DD -$803 / -$1,022 / -$10,185 | 8.5 / 6.8 / 8.6 |
| Shuffled flags (10 seeds) | $279 / $48 / -$37 | 44.5/26.1 · 36.8/20.4 · 21.9/41.9 | $1,154 / $1,025 / $113 a month | same |

- **Why it fails:** the same flip as the in-day streak. After 5 losing-sum trades, the next trade averages +0.12R / +0.06R
  in 2026 H1 / H2 but **+0.06R** in 2021-25, where the "warm" trades average -0.03R. Over five years a cold BLITZ is
  followed by better trades, not worse ones.
- **The other cells:** none passes H2 and 2021-25 together. x1.5 when cold raises the 2-week fail rate in every span
  (H1 33.6-41.2% vs 23.5%).
- **Verdict:** rejected. Do not retry BLITZ equity-curve / streak sizing without a new fact.
