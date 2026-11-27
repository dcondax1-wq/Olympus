# Order flow v5: eight families, ranked after the adversarial reviews

Paper research only. Nothing here changes a live or paper rule. Every number comes from a family's own run, re-run and checked by a separate reviewer. Where the reviewer found a mistake, the corrected figure is used (each family's REVIEW.md has the details).

## Plain answer

- **No new order-flow edge was found.** After review, none of the 8 families has a YES-candidate.
- **Lane A's own idea is still the only thing that works:** fade a known level when the bar is absorbed. Its control run gives 63 trades, +0.30R, +$2,648 at 1 micro. The first absorbed signal of each day carries it: 40 trades at +0.48R.
- The top two families (targets, combo) are **lane A with one tweak**. Both tweaks are unproven. In-sample they add $200-$600 over 51 days, and those gains depend on a few trades.
- The other six either lose or look positive only because of 1-micro sizing (a few wide-stop winners). At house sizing ($500 risk, size follows the stop), exhaustion X1 loses $11,633 and delta O2 loses about $163.
- Tonight's out-of-sample check decides (new days only, rules frozen). Run `bash research/orderflow/v5/run_oos.sh`.

## Setup shared by all eight

- 51 day files, 2026-09-27 to 11-26. **Only 44 are real trading days.** The other 7 are Sunday-evening files with no regular session. Trades/week below uses 44 days (8.8 weeks), so it is about 14% higher than the families' own figures.
- Costs are in every R and $ number: $1.90 round trip, 2-tick stop slip, market fallback +18 ticks. Entry is E5 (limit at the level for 5 minutes, then market) unless a family says otherwise. $ is at 1 micro.
- Known shared bug in lane A's level code (it was there before this work): on 7 of 9 Mondays the "previous day" is the Sunday file, so those Mondays have no prior-day high/low.
- Thanksgiving (11-26, a half day) was traded in some families, against their designs.
- Over 50 variants were tried across the 8 families on the same 51 days. Holm only corrects within each family, so any single in-sample win here is weaker than it looks.

## Ranking

| # | family | best variant | trades/wk | win % | mean R | PF | $ at 1 micro (51 days) | verdict after review | what tonight's out-of-sample check must show |
|---|---|---|---|---|---|---|---|---|---|
| 1 | targets | T3R: lane A entry, 3R target instead of 2R | 4.5 | 52.5 | +0.85 | 2.68 | +$3,448 (DD $629) | **Weak.** The edge is the absorption entry, not the exit. The gain over 2R is +$615 and unproven (paired p 0.22); it is +$212 without the best trade. | T3R beats 2R in **both** OOS halves, judged on the 1m-path days (the 5m path flatters wide targets). Otherwise keep 2R. |
| 2 | combo | C2: lane A fade only when a LIT level was swept on the same side | 6.3 | 49.1 | +0.39 | 1.76 | +$2,849 (DD $1,164) | **Weak.** Placebo p 0.088, Holm 0.53. It really only filters out opening-range-high fades: 8 trades removed, about +$200 over lane A. Above the 2-4/week band. | C2 beats plain lane A (C0) on the same new days, and the filtered-out trades lose again. |
| 3 | profile | P6: absorbed fade of a prior-day value-area edge, target prior POC | 1.7 | 46.7 | +0.37 | 1.92 | +$595 (DD $166) | **TOO FEW, not weak.** 15 trades; its own edge is not significant (p ~0.2) and rests on its 2 best winners. Same idea as lane A at another level. | At least 20 new trades, mean R above 0 in both halves, and absorbed fades beating non-absorbed ones on more than 1-4 trades. |
| 4 | sessions | S3: lane A at NY midday 10:30-13:30 | 4.3 | 42.1 | +0.15 | 1.26 | +$669 (DD $1,319) | **Effectively NO.** Its profit is lane A's own 23 trades (+0.48R); the 15 midday-only trades lose (-0.35R). About -$5 without its best trade. DD about $2,800 at $500 risk. | The midday-only trades (the ones lane A would not take) make money on their own. Expect not. |
| 5 | delta | O2: trade the overnight cumulative delta direction at 09:35, out by 10:30 | 5.0 | 38.6 | -0.01 | 1.19 | +$620 (DD $1,374) | **NO in practice.** "Weak" only on the 1-micro $. In R it is flat (PF 0.99), about -$163 at $500 risk, and -$521 without its 2 best days. | Mean R clearly above 0 (not only $) and positive in both halves. O1 must survive without its best day. |
| 6 | trapped | C3: heavy-delta breakout of a new RTH high/low that holds, buy/sell the retest | 1.1 | 50.0 | +0.19 | 1.61 | +$494 (DD $342) | **NO.** 10 trades, p 0.12, Holm 0.73 over 6 tests. No delta threshold from 3% to 12% makes the label work. | The delta label separates winners from losers (labelled minus unlabelled gap above 0 in both halves), with 20+ trades. |
| 7 | exhaustion | X1: fade a new 1-hour extreme when aggression thins into it | 9.2 | 27.2 | -0.26 | 1.47 | +$1,461 (DD $1,118) | **NO.** The +$ is a sizing artifact: -$11,633 at house sizing, median trade -1.05R. Trades far too often. | Mean R above 0 and money at house sizing. Expected to fail. |
| 8 | levels | L2: absorption at Globex VAH/VAL/POC | 4.5 | 22.5 | -0.48 | 0.76 | -$652 (DD $1,162) | **NO.** None of the 6 new level types works. Negative before costs and with a plain next-open entry too. | Nothing to prove; scored only to check that the NO holds. |

How they are ordered: first, the family survives review and makes money in R; then, how much of the result rests on a few trades; then, sample size. Families 5-8 are NO in practice, so their order among themselves matters little.

## What the reviews added (not rule changes)

- **Live paper lane A will trade more than the 4/week its backtest showed.** The backtest only ever took the first absorbed signal of each day. With one position at a time it takes 63 trades, about 7.2/week on 44 days (4.5 of them first-of-day). The extra trades are about flat (-0.03R). The forward gate for lane A should judge first-of-day and later trades separately.
- The Sunday-as-previous-day bug affects lane A's levels and `engine/of_paper._prev_summary` (live looks back 1 day). It is for the lead to fix, with a test. Nothing in `engine/` was touched here.
- A pattern that keeps coming up: positive $ at 1 micro with flat or negative R means a few wide-stop winners are carrying it. Judge new days in R and at house sizing, not only at 1 micro.

## Tonight

1. Pull the new days: `python tools/data_pull.py --latest --of`
2. Score all eight frozen families on them: `bash research/orderflow/v5/run_oos.sh` (writes `research/orderflow/v5/oos_run.log`)
3. Only a family that meets its "must show" column above on the new days goes on to the proof protocol (2026 halves, and 2021-25 where bars exist). Everything else stays research.
