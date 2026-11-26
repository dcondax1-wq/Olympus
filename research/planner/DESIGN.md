# Business planner (big-evalsizer, 2026-11-26): pre-registered design, committed BEFORE any scored run

PAPER RESEARCH ONLY: nothing bought, nothing armed. Question (lead): from TODAY's 4 accounts, when to buy the next eval, which
plan, how many in parallel, when to STOP buying (a bad-market tripwire that works), and the monthly cash flow (p10/p50/p90)
over 6 and 12 months.

## Engine (reused)
research/plans/rank.py eval / funded objects (as research/badcase, research/evalsizer T0 = today's sizing), tools/forecast.py's
start-from-today code. ALL accounts of one path step on the SAME session (one market for the whole business, correlated).
Start state (board 2026-11-26 11:50 ET): Zlarior Builder 50K eval -$822.48, floor -$1,831.80, 28 sessions done, LIT;
Zlarior 25K #2 eval +$19.24, floor -$976.38, 6 done, LIT; Rapid EOD 25K eval -$4.76, floor -$1,000, 4 done, LIT + ATLAS;
ATLAS Builder 25K funded +$401.38, floor -$598.62, ATLAS. Lanes for new buys: Builder 50K = LIT, Builder 25K = LIT, Rapid
EOD 25K = LIT + ATLAS, Rapid EOD 50K = LIT + ATLAS, ATLAS's funded lost -> a Builder 25K eval with ATLAS (its own lane).
Prices: $91.80 / $63 / $97.20 / $165. Pass -> funded after rank.GAP sessions; funded lost or graduated -> that lane re-buys
(if the buy policy and the tripwire allow). MFFU limits: funded Builder 50K x1, Builder 25K x2, Rapid EOD 25K x3,
Rapid EOD 50K x3, 5 funded in all, 10 evals: a lane is opened only if its plan's (evals + funded) stays within its funded cap
and all lanes within 5.

## Markets (1,000 paths x 252 sessions, 5-session blocks)
G = 2026 Jan-Oct 16 | B = 2021-11..2025 | M25 = each block from 2026 with prob 0.25, else 2021-25 (the fragility audit's
"trust ~25% of 2026") | SW = 2026 blocks for the first 63 sessions (3 months), then 2021-25 (the market turns: the case a
tripwire exists for).

## Buy policies (stage 1, each with no tripwire)
K0 today: the 4 accounts' lanes re-buy their own plan when an eval / funded ends
K1 run-off: no new buys at all (cash floor)
K2 K0 + a 2nd Rapid EOD 25K lane (LIT + ATLAS)
K3 fill the limits: K0 + 2nd Rapid 25K + 3rd Rapid 25K... capped: Builder 50K x1, Builder 25K x2 (LIT + ATLAS lanes), Rapid 25K x2 (5 lanes)
K4 cheap: K0 but the Builder 50K lane re-buys a Builder 25K (LIT) instead, Rapid re-buys a Builder 25K (LIT) too
K5 K0 + a Rapid EOD 50K lane (LIT + ATLAS) in place of the Rapid 25K re-buy

## Tripwires (stage 2: on K0 and on the stage-1 pick; existing accounts keep trading, only NEW buys stop)
W0 none | W1 2 eval fails in a row (any lane) -> stop | W2 3 in a row -> stop | W3 LIT's last 40 live trades sum < 0R -> stop |
W4 paper-gated: buy only if the latest finished SHADOW eval passed | W5 the business (payouts - fees since today) 
$300 under its own peak -> stop.
Resume (W1-W3, W5): the shadow eval passes. SHADOW = a free Builder 50K LIT eval on the NinjaTrader Sim (the same bot,
paper), restarted at every end; it never costs or pays.

## Reported per policy x market
12-month and 6-month net $ (owner $ after split - fees) mean / p10 / p50 / p90; monthly net p10/p50/p90 (months 1-6, 7-12);
fees per month mean / p90; cash the owner needs = p90 of the deepest cumulative (fees - payouts) dip; evals bought; payouts.

## Decision rules (fixed now)
Buy policy pick = the highest M25 12-month mean net among policies whose B 12-month mean net >= K0's B net - $300.
Card (needs owner yes) if the pick != K0 AND it also beats K0 in G and SW.
A tripwire WORKS if vs W0 (same buy policy): B 12-month loss cut by >= 50%, SW 12-month net better, G net >= 90% of W0's,
M25 net >= W0's - 10% of |W0|. The working tripwire with the best SW gain goes on the card; if none works, say so.
Counted: 6 buy policies + 2 x 5 tripwires = 16 policies.
