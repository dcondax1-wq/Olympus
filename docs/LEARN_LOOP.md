# Nightly learning (owner 2026-11-15)

Owner: "an Olympian AI that constantly learns and improves everything", without spending Claude usage.

| What | How |
|---|---|
| What it does | Every evening the PC re-tests Zlarior and ATLAS on the newest bars, checks the live fills against the backtest, and tries one or two new ideas from a list. |
| Cost | Free. It runs on your PC, uses no Claude and no paid service. |
| When | Weekdays after 17:00 ET, Saturday, Sunday before 17:00 ET. Once a day. Never while a trade, a bracket or a waiting entry is open. |
| How hard it works the PC | Low priority, one CPU thread, about 1 minute a night (it stops itself within an hour). |
| What it can change | Nothing. It never touches `live_model.json`, `live_model_lit.json`, `second_model.json`, `data/account_b.json` (it checks them before and after). |
| Your phone | Quiet, unless an idea passes every test: "Candidate: X, +$Y/month in both halves - review". |
| Your part | Nothing. It starts by itself from the PC report task you already have (BOTS_BACK.bat). |

When a candidate comes: tell Claude **"review the learn candidates"**. Claude re-tests it in the run library and nothing changes until you say yes.

## The four steps
1. **Refresh.** Zlarior's backtest (the live trades re-walked: the LIT size, the live 2-week eval path at 40% of the room)
   and ATLAS's (the real account-B rules, $43 25K) on the newest TradingView exports; then the live loop itself on the
   exports + the PC's NinjaTrader bars archive (`data/nt_bars/`), so the newest days count too.
2. **Drift.** The trade reviews the bot already writes (`engine/live_learning.py`: each live / paper trade next to its
   backtest twin): missed or extra trades, live $ behind the backtest, real fill costs above 1 tick, and whether
   tonight's backtest still shows the trade a review compared against.
3. **Experiments.** `research/learn_queue.json`: ideas written down before their first run, with their cut points picked
   on Jan-Jun 2026 only. One or two a night. Judged by the same gates as every other change (costs in):
   - Zlarior: more $ in Jan-Jun (pick) AND Jul-Oct (check) at the LIT size AND on the eval path, 2-week fails not up,
     2-4 trades a week, at least 5 / 3 trades changed, and better than the same sizes shuffled at random (200 draws).
     2021-25 is shown, never a gate.
   - ATLAS: better in Jan-Jun AND Jul-Oct (2-week pass not down, dead evals not up, $ up) and 2021-25 not worse, 2+ signals a week.
   - Every result keeps net $, $ a month and the eval speed (2-week pass / fail, decided in 10, 15-session pass / fail,
     slow passes, median sessions to pass).
   When every idea has run, the oldest is re-checked whenever the bars or the live settings changed.
4. **Report.** `research/learn/latest.md` (one page), `summary.json`, `history.jsonl`, `drift.jsonl`, `results/<id>.json`.
   All machine-local (gitignored): the PC's auto-update needs a clean folder.

## Commands (PC or cloud, from the repo folder)
- `python -X utf8 -m engine.learn_loop status`: the queue and each verdict.
- `python -X utf8 -m engine.learn_loop run --force`: one night now (still skips while a trade is open). `--max 8` runs the whole queue.
- `python -X utf8 -m engine.learn_loop guard`: would it run now, and why not.
- Off: set `LE_LEARN=0`. Test: `python -X utf8 -m tests.test_learn_loop` (fast, no data run).

## Adding an idea
One row in `research/learn_queue.json`: `id`, `bot` (lit / atlas), `kind` (lit_tilt / atlas_tilt), `title`, `hypothesis`,
`registered` (date), `judged_by`, and `rule`: a list of steps `{"feature", "op", "h1_q" or "value", "mult"}` (first match
sets the size multiplier 0-1.5, a missing fact = x1). Zlarior facts are the columns of `research/lab/trade_intel.json`
(known at the fill); ATLAS facts are `tools/atlas_deep.feats`. Check "Tested and rejected" in `docs/CLAUDE_REFERENCE.md` first.

## First run (2026-11-15, cloud, the seeded 8)
| Idea | Result |
|---|---|
| Zlarior x1.25 when dealer gamma is low | rejected: only 1 Jul-Oct trade changed |
| Zlarior x0.75 the day after VIX jumped | rejected: Jan-Jun -$2,508, Jul-Oct -$2,768 |
| Zlarior x1.25 after a tight Asia session | rejected: Jul-Oct -$131 (-$35/mo) |
| Zlarior x1.25 on a level touched many times | rejected: eval path -$116 / -$398 |
| Zlarior x1.25 on an old level | rejected: eval path Jul-Oct -$34 (LIT size +$138 / +$125 a month) |
| Zlarior x1.25 on a fast fill after the CISD | rejected: random sizes do as well (p 0.89) |
| ATLAS x1.25 after Zlarior was stopped on the other side | rejected: 1 Jul-Oct trade, 2021-24 worse |
| ATLAS x0.5 on a two-way day | rejected: Jan-Jun not better, 2021-24 worse |

Nothing passed, which is the normal case. The loop keeps re-checking them as new bars come in; new ideas go in the queue.
