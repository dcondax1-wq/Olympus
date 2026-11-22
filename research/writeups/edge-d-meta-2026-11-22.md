---
title: Edge hunt lane D - meta-labeled size and re-entry on LIT's existing signals
family: risk
date: 2026-11-22
status: rejected
summary: 31 pre-registered versions (16 small-model size rules, 2 leverage controls, 13 re-entry / blocked-signal versions). Nothing wins. One size rule clears the money gate but is leverage, not skill; every re-entry version loses in 2021-25 or in 2026 H1.
---

## Headline (honest)

**Nothing beats today's LIT. Do not wire anything. No decide card.**

- Lane D asked two things: (1) can a small model size LIT's own trades better (0.5x / 1x / 1.5x), (2) does a second try after
  a stop-out, or a signal the 1-a-day rule blocks, make money.
- (1) 15 of 16 size rules fail the gate; all 12 that cut size lose in 2026 H1 (-$1.6k to -$15.7k) and the 4 up-only ones are the only ones that gain, because they are leverage. The one that clears the money gate (depth-2 tree, 12 facts, up-only
  1.5x on the top third) is **chance-level**: random multipliers of the same shape beat it in 29% (H1) / 45% (H2) of draws, a
  shuffled-label walk-forward beats it in 23% / 15%, half of its H1 gain is in-sample optimism (+$12.4k in-sample vs +$5.7k
  walk-forward), it was the best of 16, and on the funded 50K it adds $13-17 a month while the chance of losing the account in 6 months goes up (1.7 -> 2.1%, 3.0 -> 4.1%).
- (2) Re-entry after a stop-out: 14 extra 2026 trades in total, they lose in H1 (-$452, PF 0.28) and make +$3.7k in H2 on 5 trades
  (PF 6.8); 2021-25 -$440 (60 trades, PF 0.96). The pre-asked "second sweep of the SAME level, same session": 8 trades in
  the whole 631-trade history, PF 0.00-0.01 in every span. The signals the 1-a-day rule blocks, taken together, lose: H1 -$1.5k (PF 0.54), H2 +$3.6k (12
  trades), 2021-25 -$4.8k (102 trades, PF 0.73). Today's 1-a-day rule is doing its job.

## What is new vs the files already in `docs/TESTED_AND_REJECTED.md` (read first)

| Earlier study | What it did | What lane D adds |
|---|---|---|
| Meta-labeling 2026-10-23 (`meta-labeling.md`, `tools/meta_label.py`) | 102 facts, 10 models (logistic / boosting / forest), win = R >= 0.5, size 0.5-1.5 rank map; failed the strict bar | The **simple** version the brief asked for: 7 / 13 facts (sweep depth in ATR, time of day, R:R, prior-day range, VIX, last-3-trades streak), logistic or a depth-2 tree, **four** size maps incl. the brief's 0.5 / 1 / 1.5 and **up-only / down-only**, scored on today's live **eval path with the MFFU caps and the funded Monte Carlo** (`tools/lit_edge`), plus an in-sample vs walk-forward gap and a **flat-leverage control** |
| ZEUS Lab 13 single-fact tilts, regime sizing, setup grade, learn loop | hand-cut thresholds fixed on 2026 H1, one fact at a time | the thresholds are **learned monthly from the past only** and combined across facts |
| Walk-forward re-tuning 2026-11-17 | monthly refit of the strategy knobs (disp, BE, bank) | refit of a **size model**; the strategy itself is untouched |
| "Re-entry after the 15-minute cut or a BE" (lit-edge), "a 2nd trade a day re-run" (H1 -$1.0k..-5.0k), ATLAS funded re-entry, `x_resweep` | after a cut / BE, or ATLAS, or an engine flag with no money result | re-entry after a **STOP** specifically, split same level / same side / opposite side / cool-off, and the blocked-signal census by how the day's first trade ended |

## Method (the lane's rules, as in `CLAUDE.md` "Strategy changes")

- Base = today's live LIT: 631 trades (80 in 2026 H1, 40 in Jul-Oct, 511 in 2021-25; 2021-24 on 5m bars, 2026 on 1m), costs in (1 tick
  slip + $1.40 a contract), stops 1 tick beyond the sweep extreme, size from the stop, one VIX-band target banked at 8R.
  Reproduces the documented base exactly (+$5,562 / +$2,670 / +$25 a month).
- Money views, all from `tools/lit_edge.evaluate`: the LIT size rule; the live Builder 50K **eval path** (two_week, room_f 0.4
  to session 80, `engine/sizing.lit_qty` = the MFFU caps: MLL, daily loss, 30% rule, 40 micros); the funded 50K Monte Carlo
  (60% of the room <= $1,500 a trade, winner <= $2,000, 1,000 six-month paths). Size-ups never risk more than $990 incl. costs.
- Note: `.claude/skills/strategy-test/SKILL.md` and `docs/ACCOUNT_RULES.md` do not exist in this checkout. I followed the
  `CLAUDE.md` strategy-change rules and the MFFU rules already coded in the engine (`engine/sizing.py`, `engine/funded_life`).
- Meta-labeling: label win = final R >= +0.5. Refit on the first day of every month on trades whose **exit** is >= 2 days before it
  (purge + embargo), expanding window, first test month once 100 finished trades exist (before that x1), size cuts from the
  **training** predictions' thirds. Streak uses only trades that exited before the entry. No sklearn: logistic (L2, lambda 10,
  Newton) and a depth-2 gini tree are in `research/edge_hunt/d/meta_label.py`.
- Re-entry: the engine's own `second` hook with live params, `max_per_day` 3. Check: today's 631 trades are all present and
  unchanged in the widened run (0 mismatches; 769 trades in all, 138 extras). Extras are new setups with their own new stop,
  size and target, costs in. Every re-entry is scored at x1 and x0.5.
- Gate: more LIT-size $ AND eval-path $ than today's LIT in **both** 2026 halves, no more 2-week eval fails, 2021-25 LIT $ not
  worse, 2+ trades a week.
- **Variants logged: 31** (`research/edge_hunt/d/variant_log.jsonl`): 16 meta + 2 flat-leverage controls + 13 re-entry. Plus 6 census ledgers (diagnostic). Placebos: 200 shuffled-multiplier + 100 shuffled-label draws for the best 3.

## Result 1 - meta-labeled size ($ at the LIT size on the 50K, change vs plain 1x; full table in `research/edge_hunt/d/meta_label_results.json`)

Plain 1x: H1 +$33,901 ($5,562/mo, PF 4.98, DD -$2,196, 3.1 trades/wk); H2 +$9,919 ($2,670/mo, PF 2.91, DD -$1,396, 2.6/wk);
2021-25 +$1,265 ($25/mo, PF 1.01, DD -$19,426). Eval path: 2-week pass 44.5% / 39.1%, fail 0.0% / 0.0%, median pass session 11 / 12.

| Version (walk-forward) | LIT H1 | LIT H2 | 2021-25 | Eval H1 / H2 $ change | 2-week pass H1 / H2 | Gate |
|---|---|---|---|---|---|---|
| logistic 7 facts, 0.5 / 1.5 | -13,002 | -3,819 | +3,440 | -20,710 / +516 | 6.7 / 33.3 | fail |
| logistic 7 facts, 0.75 / 1.25 | -7,303 | -2,603 | +2,024 | -13,104 / +1,604 | 19.3 / 33.3 | fail |
| logistic 7 facts, down-only 0.5 | -14,099 | -3,786 | +4,303 | -20,940 / -185 | 6.7 / 33.3 | fail |
| logistic 7 facts, up-only 1.5 | +1,097 | -34 | -862 | 0 / -377 | 45.4 / 39.1 | fail |
| depth-2 tree 7 facts, 0.5 / 1.5 | -14,981 | -2,504 | +3,256 | -17,806 / +1,080 | 10.9 / 33.3 | fail |
| depth-2 tree 7 facts, 0.75 / 1.25 | -8,200 | -1,961 | +1,876 | -12,280 / +1,559 | 21.0 / 33.3 | fail |
| depth-2 tree 7 facts, down-only 0.5 | -15,736 | -3,320 | +3,093 | -18,611 / +299 | 10.9 / 33.3 | fail |
| depth-2 tree 7 facts, up-only 1.5 | +755 | +816 | +163 | 0 / -377 | 44.5 / 39.1 | fail (eval H2) |
| logistic 13 facts, 0.5 / 1.5 | -8,907 | +2,814 | +1,832 | -12,691 / +2,184 | 28.6 / 39.1 | fail (H1) |
| logistic 13 facts, 0.75 / 1.25 | -4,944 | +250 | +1,104 | -9,343 / +2,346 | 37.0 / 36.2 | fail |
| logistic 13 facts, down-only 0.5 | -9,617 | -476 | +4,214 | -12,621 / +759 | 28.6 / 39.1 | fail |
| logistic 13 facts, up-only 1.5 | +710 | +3,289 | -2,382 | 0 / +1,003 | 45.4 / 39.1 | fail (2021-25) |
| tree 13 facts, 0.5 / 1.5 | -2,952 | +1,812 | +5,444 | -13,010 / -929 | 31.9 / 26.1 | fail (H1) |
| tree 13 facts, 0.75 / 1.25 | -1,559 | -117 | +2,965 | -10,641 / +1,246 | 36.1 / 26.1 | fail |
| tree 13 facts, down-only 0.5 | -8,659 | -1,377 | +4,965 | -16,100 / -682 | 31.9 / 26.1 | fail |
| **tree 13 facts, up-only 1.5** | **+5,708** | **+3,188** | **+480** | **+3,128 / +241** | **44.5 / 39.1** | **passes the money gate, not a winner** |
| control: every trade x1.167 (no model) | +3,651 | +336 | -119 | +1,037 / +155 | 45.4 / 39.1 | fail (2021-25) |
| control: every trade x1.25 (no model) | +6,446 | +873 | +212 | +2,954 / -141 | 44.5 / 39.1 | fail (eval H2) |

Reading it:
- **Anything that cuts size loses in 2026 H1** (-$1.6k to -$15.7k): shrinking trades costs more than it saves. In 2021-25 the
  same cuts make money (+$1.1k to +$5.4k) because that is a PF 1.0 regime where cutting is cutting a coin flip. That is the same
  split the regime / drift / grade studies found: caution pays in bad years and costs in good ones.
- **Up-only is leverage.** 234 of 631 trades get x1.5 (mean multiplier 1.19). A flat x1.25 with no model makes more in H1 (+$6.4k)
  than the model does (+$5.7k). The model's edge over leverage is only in H2 (+$3.2k vs +$0.9k) on 40 trades.
- **Controls for the one pass (tree, 13 facts, up-only 1.5):** shuffled multipliers (same shape) beat it in 28.5% / 45.0% / 44.5% of
  200 draws (H1 / H2 / 2021-25); shuffled-label walk-forward beats it in 23% / 15% / 26% of 100 draws. Neither is below 5%, before
  counting that it is the best of 16 (the other two best candidates: logistic 13 up-only 0.73 / 0.10 / 0.80, tree 7 up-only 0.85 / 0.69 / 0.49).
- **In-sample vs out-of-sample gap (LIT $, same model fitted on all 631 trades vs walk-forward):** tree 13 facts up-only H1
  +$12.4k vs +$5.7k, H2 +$3.1k vs +$3.2k, 2021-25 +$4.3k vs +$0.5k; tree 13 facts 0.5 / 1.5: H1 +$13.2k in-sample vs -$3.0k walk-forward, 2021-25 +$10.6k vs
  +$5.4k. A tree fitted on everything looks like a 2021-25 genius and a +$13k H1 gain; refit month by month from the past it is -$3.0k in H1.
- **Eval path (MFFU caps):** every version that cuts size passes **fewer** 2-week evals in H1 (6.7-37% vs 44.5%) and takes longer
  (median pass session 13-29 vs 11): the two_week size is already at the caps, a cut only slows it. Up-only does not speed the eval
  either: 2-week pass 44.5 / 39.1 = today's, the caps absorb the size-ups. 2-week fails stay at 0.0% in H1 / H2 for every version.
- **Funded 50K Monte Carlo for the 3 best:** tree 13 up-only $946 / $928 / $55 a month vs today $929 / $915 / $58 (H1 / H2 / 2021-25 like),
  but 6-month account loss 2.1 / 4.1 / 54.8% vs 1.7 / 3.0 / 52.0% and any-payout 94.2 / 90.1 vs 94.5 / 92.8%. More $ by $13-17 a month
  for more ruin and fewer payouts: not worth it. Max drawdown at LIT size gets worse (-$2,379 vs -$2,196 H1, -$21.4k vs -$19.4k 2021-25).
- Overlap with the Oct 23 study: it already found that what a model learns is mostly "far target = fewer wins" (R:R alone gets
  AUC 0.58 vs 0.60), which pays back in the bigger wins, so there is nothing to size on. Lane D does not contradict that.
  A simpler 7-fact model does not rescue it. With 40 Jul-Oct trades nothing is provable; the same note (rerun after ~150 more 1m trades) stands.

## Result 2 - re-entry and blocked signals (extras only, LIT size; full JSON `reentry_results.json`)

Census, every extra trade the widened run takes (new stop, own size), by how the day's first trade ended:

| After the day's first trade ended | 2026 H1 | 2026 H2 | 2021-25 |
|---|---|---|---|
| STOP (stop-out) | 9 trades, -$452, PF 0.28 | 5 trades, +$3,685, PF 6.8 | 60 trades, -$440, PF 0.96 |
| BE | 10, -$343 | 2, +$327 | 38, -$3,671, PF 0.49 |
| TARGET | 0 | 4, +$136 | 4, -$630 |
| 15-minute cut | 5, -$680 | 1, -$593 | 0 |
| **All blocked by the 1-a-day rule** | **24, -$1,477, PF 0.54** | **12, +$3,555, PF 3.3** | **102, -$4,799, PF 0.73** |

Versions (added to today's trades, change vs today at the LIT size; gate always fails):

| Version | extras H1 / H2 / 21-25 | LIT H1 | LIT H2 | LIT 2021-25 | Eval H1 / H2 $ change |
|---|---|---|---|---|---|
| R1 after a STOP, any, x1 | 9 / 5 / 60 | -2,186 | +3,066 | -733 | -2,045 / +1,467 |
| R1 x0.5 | | -1,864 | +1,139 | -446 | -1,188 / +1,197 |
| R2 same level re-swept, same side, same session, x1 | 1 / 1 / 6 | -2,076 | -1,008 | -1,827 | -2,004 / -601 |
| R3 after a STOP, same side, x1 | 9 / 4 / 43 | -2,186 | +3,196 | -3,076 | -2,045 / +1,467 |
| R4 after a STOP, opposite side, x1 | 0 / 1 / 17 | 0 | -130 | +2,343 | 0 / 0 |
| R5 after a STOP, 30-min cool-off, x1 | 7 / 5 / 55 | -2,192 | +3,066 | +2,417 | -2,046 / +1,467 |
| R6 after anything but a STOP, x1 | 15 / 7 / 42 | -1,211 | -130 | -4,620 | -1,440 / -1,526 |
| R7 Monday rule off | 42 trades differ | -2,113 | -305 | +3,749 | -5,998 / -322 |

Reading it:
- **Stop-out re-entry loses in 2026 H1 in every form** (9 extras, 6 of them winners but PF 0.28, -$452 at x1) and H2 is
  5 trades; two-week fails stay 0.0 but the eval path in H1 gives back $1.2-2.0k. 2021-25 is flat to negative.
- **The same level, same session second sweep is the worst bucket**: 8 trades in 5 years of 2021-25 plus 2026, PF about 0 in every span (no meaningful winner).
  The count is too small to prove it either way; it certainly does not support an edge.
- **Opposite side after a stop-out** (the reversal) is +$2.3k in 2021-25 on 17 trades (PF 1.84) but **1 trade in 2026**: no evidence in the regime we trade now.
- **Blocked signals total**: 2026 H1 loses; H2's +$3.6k is 5 trades after a stop-out. Both the one-a-day rule and the weekly-stop
  size cut stand. Windows outside 02:00-15:30 were tested before (`lit-all-hours`, 00:00-15:55: no money in H1); not repeated.
- Monday-rule-off changes the trade list by 42 trades: eval H1 -$6.0k and the H2 2-week pass 39.1 -> 31.9% (median pass 12 -> 21 sessions): the rule helps.

## Overfitting summary

| Check | Result |
|---|---|
| Variants tried | 31 (+6 census ledgers); 3 best compared with placebos, so p-values are before the best-of-16 correction |
| Only version through the gate | tree 13 facts up-only: shuffled-m p 0.29 / 0.45, shuffled-label p 0.23 / 0.15 |
| In-sample vs walk-forward, LIT $ H1 | +$12.4k vs +$5.7k (that version), +$13.2k vs -$3.0k (0.5 / 1.5 tree) |
| Sample | 2026 H1 80 trades, Jul-Oct 40, re-entry extras 14 in 2026 |
| 2021-25 vs 2026 | size cuts help 2021-25 and hurt 2026; re-entry the other way round: no rule is stable in both |

## Tried and failed (all 31 + the census)

Meta size: logistic / depth-2 tree x 7 / 13 facts x (0.5/1.5, 0.75/1.25, down-only 0.5, up-only 1.5) = 16, flat x1.167 and x1.25 controls (2).
Re-entry: after a stop-out any / same level + session / same side / opposite side / 30-min cool-off, x1 and x0.5 (10), after
BE / TARGET / EOD / cut (x1, x0.5, 2), Monday rule off (1). 0 winners.

## Files

`research/edge_hunt/d/` : `common.py`, `meta_label.py`, `reentry.py`, `control_leverage.py`, `*_results.json`, `variant_log.jsonl`,
`reentry_stdout.txt`. Reproduce: `python -X utf8 research/edge_hunt/d/meta_label.py` (2.5 min), `reentry.py` (<1 min), `control_leverage.py`.
Recommendation: keep today's LIT unchanged. Re-run the meta part when LIT has ~150 more 1m-bar trades.
