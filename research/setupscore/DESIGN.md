# LIT live setup score: pre-registered design (written 2026-11-26 BEFORE any score was computed; not changed after results)

Lead's ask (big-setupscore): for every LIT setup the live bot sees (taken or skipped), show "similar setups: N, win rate X%,
avg +Y R, $ at today's size" from history. DISPLAY ONLY: it never changes which trades are taken, sizes or routes anything.
And say honestly whether the score separates winners from losers out of sample.

## History pool
Every LIT setup since 2021-11 from `tools/lit_setups_learn.funnel` (the real engine, live parameters): 8,784 setups, of which
2,302 have an outcome: the 638 TAKEN trades (their real R, costs in) + 1,664 setups that would have filled with every gate
open ("would", the engine's own one-at-a-time replay). Setups that never filled / overlapped another trade have no outcome and
are not in the pool. Rows: `research/setupscore/rows.json.gz` (`rows.py`).

## Features (only what the live bot knows at the 5m CISD bar AND carries in its Brain setup row)
time of day (ET minutes / 60), sweep depth (ATR), displacement (ATR), inducements taken (capped at 3), prior VIX close; the
SIDE must match exactly (longs score against longs). Not used, said not hidden: day type (big-regime: the day-type call had no
out-of-sample information), ES agreement (ES bars only from 2025-04), order flow (no tick history yet), target distance
(only known once a limit is armed).

## Score
k-nearest neighbours: each feature standardised by the pool's standard deviation, Euclidean distance, same side, k = 50,
pool = rows dated BEFORE the scored setup's day (causal). Score = the neighbours' mean R; also their win rate and N. Shown
in $ as mean R x the trade's $ risk at today's size when the risk is known (an entry), else in R only.
Baseline for comparison: the learner's existing bucket lookup (`lit_setups_learn.similar`: session, TDO side, depth / disp bands).

## Out-of-sample test (does the score separate winners from losers?)
Holdout A (the main one): score every 2026 Jul-Oct setup with an outcome using a pool FROZEN at 2026-06-30.
Holdout B (second look): 2026 Jan-Jun with the pool frozen at 2025-12-31.
Reported for all setups with an outcome AND for taken trades only:
- Spearman rank correlation of score vs realised R, with a permutation p (2,000 shuffles, one-sided).
- Mean realised R of the top third of scores vs the bottom third; win rate of each third.
- AUC of the score for win (R > 0).
**Separates** = in BOTH holdouts, on the all-outcome set: Spearman > 0 with p < 0.05 AND top-third mean R > bottom-third
mean R. Anything less = **info only**: the display then says "history only, not a predictor" next to the numbers.
Even a "separates" verdict changes nothing about which trades are taken: a rule change would need its own CLAUDE.md proof.

## Live hook rules
`engine/setup_score.py` is pure and never raises (returns None on any problem); it reads a frozen pool file
(`research/setupscore/pool.json`, rebuilt nightly by `tools/setupscore_build.py`). It is called only from code that already runs
off the order thread: `engine/setup_progress` (watchdog, every 30 s) and `engine/notify.entry_message` (the daemon thread of
`engine/push.pc_notify`), each inside try/except. Checks: `python -X utf8 -m tests.test_lit_live` (live loop = backtest, 0 diffs)
and `tools/update_gate.py` (SAME).
