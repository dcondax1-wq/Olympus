# Lane A stress test: pre-registered (written 2026-11-27 ~00:20 ET, BEFORE any of the tests below were run)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, a setting or an arming. Code: `research/orderflow/lanea_proof/proof.py`;
output `research/orderflow/lanea_proof/results.json`; write-up `research/writeups/lanea-proof-2026-11-27.md`.

## What is being tested
Lane A exactly as frozen in `DESIGN_paper.md` (absorbed level fade: PD H/L, Globex H/L, ORB H/L from 10:00; 09:45-15:00 ET signal
bars; absorbed = zone dz x d < 0 and |dz| >= 0.20 x vz; stop 1 tick beyond the signal bar's extreme; target 2R; flat 15:55; one
position at a time), replayed with `engine/of_paper.replay_summary` on the 51 real NQ tick-summary days (2026-09-27..11-26) the
PC sent. Look 1 (`real_verdict.md`) found TAKEN 40 trades +0.49R vs SKIPPED -0.31R, p 0.0065, halves +1.40R / +0.11R gap.
These 51 days were already seen once by look 1: this is a STRESS test of one candidate on the same days, not a new discovery,
and it cannot turn the candidate into a proven edge. Only forward days can. No rule, level, threshold or target is tuned here;
the splits below are DESCRIPTIVE (n is too small to pick a sub-group, and picking one would be curve-fitting). No sub-group is
promoted from this file.

## Costs (all tests)
$1.90 round trip per micro (engine/costs.COMM_RT), MNQ $2/pt. Stop fills 1 tick worse than the stop (as the paper bot).

## Fill models (each re-simulated on the same 5m bars, same stop/target/15:55 rules)
- F1 = baseline: market after the decision = next bar open + 1 tick (the paper bot).
- F2 = next open + 2 ticks.  F3 = next open + 3 ticks.  (+1 / +2 ticks worse than the baseline.)
- FS = F1 with stop fills 2 ticks worse (not 1).
- FL = a LIMIT at the swept level price, live for the 3 bars after the signal bar (15 min): filled only if a bar trades
  through the level by >= 1 tick (a touch is not a fill: queue position unknown); risk/target recomputed from the level fill;
  if the fill bar also reaches the stop -> counted as a stop (worst case). Unfilled = no trade (counted, reported as a miss).
Target stays 2R of the FILLED risk in every model (as the paper bot computes it).

## Reported for each model: n, trades/week, win %, mean R, PF, net $ at 1 micro, $/month at 1 micro, max DD (1 micro, closed-trade
equity), and the TAKEN minus SKIPPED gap (skipped re-simulated with the same model).

## Splits (F1, descriptive only)
level type (pd = pdh/pdl, glob = Globex high/low, orb = orh/orl); time of the signal bar (09:45-10:30, 10:30-12:00, 12:00-15:00);
absorption strength |dz|/vz in thirds of the taken trades; long vs short; walk-forward by ISO week (mean R and sum R per week,
how many weeks > 0); day-block bootstrap of TAKEN mean R (10,000 resamples of days, seed 11): 90% and 95% CI, P(mean R <= 0).

## The halves problem (why is the newer half weaker?) - diagnostics, decided in advance
For older (first 25/26 days) vs newer: candidates per day, taken share, taken mean R, skipped mean R, mean signal-bar risk in
ticks, mean daily RTH range (points), the share of trend days (|close - open| >= 0.6 x range), share of exits by target / stop /
15:55, level-type mix of taken trades. Plain-words read: is the weak half fewer setups, a different regime, or the same setups
working less?

## Overlap with LIT / ATLAS
LIT trades = `of_battery.lit_trades()` (the frozen live model's replay on the futures bars, entry time te/tn), ATLAS MD trades =
`of_battery.atlas_md()`, both on 2026-09-27..11-26. Overlap = a lane A trade open (fill..exit) at a LIT or ATLAS entry, or the
reverse. Reported: how many lane A trades overlap, and the lane A R of the overlapping vs not overlapping ones. On one account
with one-position-at-a-time the later one is blocked.

## Eval / funded engines (research/plans/rank.py machinery, the live sizing rules, nothing changed)
Plans: MFFU Builder 50K, Builder 25K, Rapid EOD 25K (eval + its funded life), and the 25K funded (Builder) life.
Streams: (a) lane A alone, (b) LIT + ATLAS (today's), (c) LIT + ATLAS + lane A. Lane A is an "added strategy" sized like ATLAS
by `stack_one_account.stack_q` (usd $250 on a 25K / $500 on a 50K, f 0.3 of the room, the soft daily loss), LIT stays at
`sizing.lit_qty` (the live two_week, room_f 0.4 to session 80). Paths = day-block bootstrap (blocks of 5 sessions) of the 51 real
days ONLY (lane A exists nowhere else), 2,000 paths, 60 sessions for the eval, 126 for the eval+funded slot; LIT/ATLAS on those
same days from the replays above (so (b) is today's bots on the same 51 days). Reported: pass %, fail %, median days to pass,
max DD, $/month (slot net incl. fees at the owner's real prices: 50K $91.80, 25K $63, Rapid 25K $97.20). Honest caveat written
now: 51 days resampled = one regime; these numbers are a smoke test of fit, not a forecast.

## Bars decided now
**Worth a Sim101 forward test next week** if ALL: (1) F2 (+1 tick worse) TAKEN mean R > 0 after costs; (2) the F1 bootstrap
90% CI lower bound of TAKEN mean R > 0; (3) TAKEN mean R > 0 in both halves at F1; (4) adding lane A to LIT + ATLAS does not lower
the eval pass % by more than 2 points on any of the plans. A fail on (1) or (3) = keep it paper-only (the shadow bot logs it
anyway), no Sim101 order routing.
**The forward gate that would make it an owner card for the evals** (days from 2026-11-27 only, real Sim101 / paper fills):
>= 30 resolved TAKEN trades AND mean R >= +0.20 after costs AND PF >= 1.30 AND TAKEN mean R > SKIPPED mean R AND neither half of
the forward trades below 0R AND max DD <= 6R. Under 30 trades = TOO FEW, keep running. Fail = REJECTED, written into STRATEGY.md
"Tested and rejected".
