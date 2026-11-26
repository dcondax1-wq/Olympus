# Business planner: what to buy, when to stop, what cash to expect (2026-11-26)

PAPER RESEARCH ONLY (nothing bought). Design first: `research/planner/DESIGN.md`. Code `research/planner/planner.py` ->
`results.json` (pre-registered run kept as `results_prereg.json`). Engine = rank.py eval / funded objects (today's sizing, ATLAS
lane, every MFFU rule and limit), ALL accounts on the same sessions, start = the board 2026-11-26 (50K eval -$822, 25K #2
+$19, Rapid 25K -$5, ATLAS funded +$401). 1,000 paths x 12 months. Markets: 2026-like | 2021-25-like | 25% mix (the fragility
audit's "trust ~25% of 2026", the PLANNING case) | turns bad after 3 months.

## The one page
| 12 months, net $ after fees (p10 / p50 / p90) | 2026-like | 25% mix (plan on this) | 2021-25-like | turns bad |
|---|---|---|---|---|
| **today's plan** (re-buy each lane) | $38,399 (19.7k / 38.5k / 57.0k) | $2,651 (-1.5k / 1.4k / 8.8k) | -$667 (-2.0k / -1.4k / 1.6k) | $6,488 |
| **today + tripwire W3 (the card)** | $37,956 | $2,557 (-1.1k / 1.1k / 8.4k) | **-$202** | **$6,865** |
| run-off (buy nothing more) | $27,042 | $1,525 | +$288 | $6,794 |
| + 2nd Rapid EOD 25K | $60,450 | $2,892 | -$1,194 | $8,675 |
| Rapid 50K instead of Rapid 25K re-buys | $47,100 | $3,687 | -$1,104 | $6,219 |
| cheap (50K and Rapid re-buy 25Ks) | $29,514 | $2,067 | +$112 | $6,702 |
6 months, today's plan: 2026-like $16,045 (4.7k / 15.8k / 28.0k), 25% mix $967 (-0.8k / 0.1k / 4.3k), 2021-25 -$372.
Monthly net, today's plan, p10 / p50 / p90: 2026-like months 1-6 $0 / $1,600 / $7,116, months 7-12 $0 / $3,217 / $8,145;
25% mix -$223 / -$63 / $800 then -$223 / -$63 / $1,537 (most months are fees; the money comes in a few payout months).
Eval fees: $29 a month in a 2026-like market, $94 (p90 $132) in the mix, $134 (p90 $168) in 2021-25-like. **Cash the owner
should keep for fees: ~$1,500** (p90 deepest dip in the mix; $2,000 if 2021-25-like; $1,100 / $1,360 with the tripwire).

## Decision rules (what to do)
1. **Buy:** keep today's lanes and re-buy the same plan the day an eval fails or a funded account ends (Builder 50K, Builder
   25K, Rapid EOD 25K; ATLAS's 25K re-buys a 25K for ATLAS). Pre-registered pick = today: a 2nd Rapid 25K or Rapid 50K
   re-buys earn far more in a 2026 market but lose $440-530 more a year in a 2021-25 one (outside the bar).
2. **Stop buying (card):** when LIT's last 40 trades sum < 0R. Existing accounts keep trading. **Restart** when a free Sim
   eval (Builder 50K rules, same bot, paper) passes. Today: last 40 = +30R, not near the line.
3. **How many:** at most 5 funded-capable lanes (MFFU: 5 sim funded in all). Today uses 4.
4. **Expect:** plan on the 25% mix: ~$1,400 median in 12 months, 34% chance of a losing year (37% with the tripwire: it
   stops some re-buys that would have paid); the 2026-like $38k is the upside, not the plan.

## Tripwires (pre-registered bar: 2021-25 loss cut >= 50%, better when the market turns, >= 90% of 2026-like $, mix not >10% worse)
| on today's plan | 2021-25 | turns bad | 2026-like | 25% mix | works |
|---|---|---|---|---|---|
| none | -$667 | $6,488 | $38,399 | $2,651 | - |
| W1 2 fails in a row | -$18 | +$388 | -$181 | -$312 | no (mix -12%) |
| W2 3 fails in a row | -$113 | +$324 | -$51 | -$208 | yes |
| **W3 LIT last 40 trades < 0R** | -$202 | **+$377** | -$443 | -$94 | **yes (pick: best "turns bad")** |
| W4 buy only after a Sim pass | -$156 | +$239 | -$1,401 | -$405 | no |
| W5 business $300 under its peak | -$114 | +$333 | -$21 | -$199 | yes |
The earlier rolling-expectancy rule (badcase) failed as a TIMING signal for single evals; as a BUY GATE with a Sim-pass restart,
W2 / W3 / W5 all pass. W5 is the simplest and cheapest in a good market; W3 won on the pre-registered "turns bad" tie-break.

## Post-hoc (NOT pre-registered, flagged): a 2nd Rapid 25K + a tripwire
K2 + W5: 2026-like $60,336 (+$21,937 vs today), turns bad $9,273 (+$2,785), 2021-25 -$311 (better than today's -$667),
mix $2,604 (-$47). With the $300-drawdown gate the 2nd Rapid's bad-market cost goes away. This is the best money idea found,
but it was chosen after seeing the numbers. **Fresh-path check** (new seeds 101-104, `fresh_check.py` -> `fresh_check.json`):
| 12 months | 2026-like | 25% mix | 2021-25 | turns bad | cash to keep (p90, mix / 2021-25) |
|---|---|---|---|---|---|
| today | $37,598 | $2,425 | -$705 | $6,514 | $1,517 / $2,040 |
| today + W3 | $37,140 | $2,378 | -$207 | $6,890 | $1,134 / $1,323 |
| **2nd Rapid 25K + W5** | **$58,813** | **$2,480** | **-$279** | **$9,394** | $1,271 / $1,334 |
It beats today in all 4 markets on fresh paths -> second card (labelled post-hoc: same history, new paths only).

Caveats: block bootstrap; 2026 is LIT's pick period (hence the 25% mix); ATLAS funded on its research lane; the Sim shadow eval
needs building (paper); Builder 50K funded vs ATLAS 25K funded conflict read per the limits article; K3 = K2 by the 5-lane cap.
