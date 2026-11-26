# LIT learns from live (day-litlearn 2026-11-26)

**In plain words.** Every LIT setup the bot sees is now recorded: how far it got through the 10 steps, why it stopped, and what it made
or would have made. That covers 8,784 setups from Jan 2021 to Nov 20 2026, and 638 of them were taken. Each night the loop
(1) measures what each step's rule earned or cost in $, (2) lists the newest days' setups with "setups like this one won X of Y",
and (3) re-tests 13 rule changes, written down in advance, through the CLAUDE.md proof bar automatically. **Today none pass, so
nothing is proposed.** Nothing live changed. The loop only writes research files (`research/learn/`).

Run: `python -X utf8 tools/market_learn_weekly.py --nightly --litlearn`, about 20 s for the whole nightly (the setup step is ~14 s with
the replay cache warm). On its own: `python -X utf8 tools/lit_setups_learn.py [--out logs/learning]`.
Tests: `python -X utf8 -m tests.test_lit_setups_learn` (25 checks, nq area).

## Where setups stop (2021 -> Nov 20 2026, the live model)
| step (Brain words) | setups | would-have outcome known | won | avg R |
|---|---|---|---|---|
| 0 outside 02:00-15:30 | 745 | 241 | 102 | -0.18 |
| 2 sweep too shallow (< 0.5 ATR) | 642 | 146 | 68 | -0.27 |
| 3 no inducement | 2,486 | 592 | 281 | -0.02 |
| 4 displacement too small (< 0.8 ATR) | 1,469 | 455 | 216 | +0.02 |
| 6 limit not armed (stop size) | 24 | 24 | 16 | +0.17 |
| 7 never filled (no tap / no 1m CISD) | 2,579 | - | - | - |
| 9 blocked by a day rule | 201 | 201 | 94 | -0.04 |
| **8 TAKEN** | **638** | 638 | 344 | **+0.16** |
"Would have": the same engine with every gate open, one trade at a time. A setup that overlapped another open trade has no
would-have outcome (shown as "overlapped"). "Never filled" has none by definition.

## Gate ledger: what each rule is worth (each opened alone, real engine and sizing, costs in; + = the rule earns)
| step | rule | Jan-Jun 2026 | Jul-Nov 20 2026 | 2021-25 | missed winners $ | avoided losers $ | verdict |
|---|---|---|---|---|---|---|---|
| 4 | displacement body >= 0.8 ATR | +6,829 | +4,396 | +9,473 | 77,119 | 72,485 | earns |
| 7 | the limit lives 6 bars | +4 | +444 | +8,786 | 544 | 7,628 | earns |
| 2 | sweep >= 0.5 ATR | +1,898 | +1,029 | +5,038 | 4,928 | 13,876 | earns |
| 6 | stop 8-80 points | +628 | +116 | +3,597 | 7,533 | 9,084 | earns |
| 0 | entry hours 02:00-15:30 | +5,412 | -660 | +8,525 | 12,022 | 24,037 | mixed |
| 7 | 1m CISD within 22 bars | +14,487 | +5,154 | -8,496 | 93,629 | 201,543 | mixed |
| 3 | inducement within 1 ATR | +4,567 | +3,693 | -91 | 47,746 | 47,476 | mixed |
| 9 | one trade a day | +4,958 | -2,565 | +5,626 | 16,619 | 21,485 | mixed |
| 9 | weekly stop | -1,453 | +233 | +621 | 0 | 0 | mixed |
| 6 | VIX-band target >= 1.5R | -353 | +398 | -1,052 | 1,917 | 846 | mixed |
| 9 | Monday rule | +2,113 | +302 | -3,749 | 7,038 | 6,495 | mixed |
- No rule costs money in all three spans. Four earn in all three. The biggest saver in 2026 is the 1m CISD wait (+$19.6k over
  Jan-Nov), but it gives back $8.5k in 2021-25. The two-way columns show what the rule saw: the displacement rule threw away $77k of
  winners and $72k of losers, and the $ value comes from sizing and knock-on effects (one trade at a time, one a day).
- The weakest rules (mixed, small) are the Monday rule, the VIX-band minimum target and the weekly stop. They are worth watching, not changing.

## Suggestions through the proof bar (13 pre-registered, 0 pass)
Bar, all automatic: beat live on 2026 Jan-Jun (net + PF) AND Jul-Nov 20 (net + PF), 2021-25 net not worse, walk-forward >= 5 of 7
blocks (2021..2025 yearly + 2026 H1 / H2), 2-4 trades a week in 2026, and not already in `docs/TESTED_AND_REJECTED.md`.
| change | Jan-Jun | Jul-Nov 20 | 2021-25 | walk | already rejected? |
|---|---|---|---|---|---|
| displacement >= 0.6 | +1,615 | -3,413 | -16,195 | 1/7 | yes |
| displacement >= 1.0 | -10,211 | -6,672 | -14,512 | 1/7 | yes |
| sweep >= 0.3 | +1 | -617 | -1,337 | 2/7 | yes |
| sweep >= 0.75 | +1,029 | -4 | -3,662 | 4/7 | no (now logged) |
| no inducement | -4,567 | -3,693 | +90 | 2/7 | yes |
| 2 inducements | -19,514 | -4,880 | -2,105 | 3/7 | no (now logged) |
| limit lives 12 bars | -4 | -444 | -8,787 | 0/7 | no (now logged) |
| 1m CISD within 15 bars | -10,565 | -1,504 | -2,815 | 2/7 | no (now logged) |
| a 2nd trade a day | -4,958 | +2,565 | -5,626 | 3/7 | yes |
| no Monday rule | -2,113 | -302 | +3,749 | 2/7 | yes |
| Silver Bullet hours only | -29,754 | -9,139 | -3,346 | 3/7 | yes |
| True Day Open side only | -7,708 | -2,344 | +4,133 | 3/7 | yes |
| skip prior VIX >= 25 | -4,065 | 0 | -10,009 | 4/7 | yes |
All 13 are now "watching" lines in the journal and are re-tested every night. A full pass would become an
"adopted-needs-owner-yes" card. The owner's yes AND a hand re-run of the full proof (`strategy-test`) would still both be needed
before anything goes live. 13 tests means a lucky pass is possible (about 1 in 20 per test at the usual bar), so a card is a reason
to look, not a decision.

## Setups like today's (the newest 3 sessions, from `lit_setups.json` review)
Example lines (Nov 20, VIX 25+ week):
- 11-20 03:35 short: stopped at step 4 (displacement too small); would have made +3.94R. Setups like it (London, discount, 1.5+, <0.8, VIX 25+, short) won 9 of 15, avg +0.23R.
- 11-20 07:55 long: stopped at step 4. Setups like it (London, discount, 1.5+, <0.8, VIX 25+) won 14 of 24, avg +0.57R.
- 11-20 09:35 short: never filled (step 7). Setups like it (NY AM, premium, 1.5+, 1.2+) won 27 of 52, avg +0.04R.
"Like it" = the same session, True Day Open side, sweep-depth band, displacement band, VIX band and side. The last field is dropped
(side first, then VIX...) until at least 15 earlier setups match. Only setups BEFORE that day count.

## What it reads, what it writes
- Reads: the cached LIT replay (`tools/lit_final.market`, 2021 -> the newest bar on disk; the backtest list plus the live twin's newer
  weekdays), `live_model.json` (read only), `data/VIX_1d.csv`, and the PC's day folders `data/pc_days/<day>/decisions.jsonl.gz` (the
  Bot Brain's armed / expired / rejected words) + `trades.jsonl.gz` (live LIT trades) when present: matched to a setup within 15 min.
- Writes: `research/learn/lit_setups.json` (everything; ~40 KB), journal lines (`litlearn|gate|*`, `litlearn|prop|*`,
  `litlearn|day|*`; lens "setup gate" / "setup suggestion" / "setup review"), the Brain's LIT room = `brain_state.json`
  `pillars.lit.setups` (funnel, costs / earns most, the newest sentences, owner cards). On the PC use `--out logs/learning`.
- Not yet: day-type (waits for the big-regime work) and the order-flow state (waits for the tick days). Both are fields in every
  row (`day_type`, `of_state`) set to None.
