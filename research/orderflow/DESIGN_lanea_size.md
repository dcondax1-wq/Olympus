# Lane A size test: pre-registered (written 2026-11-27 ~00:30 ET, BEFORE any size result was run)

PAPER RESEARCH ONLY. Nothing changes a bot, size, setting or arming. Code `research/orderflow/lanea_proof/size.py`, output
`research/orderflow/lanea_proof/size_results.json`, added to `research/writeups/lanea-proof-2026-11-27.md`.
Follows `DESIGN_lanea_proof.md`, whose bar 4 failed: lane A at ATLAS-style size ($500 on a 50K / $250 on a 25K, 30% of room) roughly
doubled the eval fail % and the funded blow-ups. The question: what is the LARGEST lane A size that does not hurt the evals?

## Fixed inputs (as the stress test)
Lane A taken trades = F1 fills (next open + 1 tick), $1.90 rt, stop 1 tick worse, target 2R, from the 51 real days 2026-09-27..11-26.
LIT (frozen model replay, live `sizing.lit_qty`, two_week room_f 0.4 to session 80) + ATLAS MD (stack_q, $500 / $250) as today.
Engines: `research/plans/rank.py` spec (eval `rapid_levers.Ev`, funded `rank.Funded`) for MFFU Builder 50K ($91.80), Builder 25K
($63), Rapid EOD 25K ($97.20, news rule). The 126-session slot = the eval and then its funded life; "funded 25K" is read from the
Builder 25K slot (funded blow-up % = runs where a funded account was lost). 1,000 day-block bootstrap paths (blocks of 5), fixed
seeds, the SAME paths for every variant (common random numbers). 60 sessions for the eval-only numbers.

## Lane A size variants (micros per trade; 0 = the trade is skipped)
- Q1 / Q2 / Q3: fixed 1 / 2 / 3 micros (still capped by the plan's max micros and stopped by the soft daily loss, as stack_q).
- C50 / C100 / C150: risk cap $ = floor(cap / (stop pts + 1 tick) x $2 + $1.90). Lane A stops are wide (~50-75 pts = $100-150 a
  micro), so C50 skips almost everything; reported with the share of trades that get >= 1 micro.
- REF: last night's ATLAS-style stack_q ($500 / $250, 30% of room) for comparison.
## Gates (account state at the START of the session, from the engine's own balance; balances start at $0)
- none.
- UP: lane A only once the balance is >= +X above start (X = $1,000 on a 50K, $500 on a 25K).
- FLOOR: lane A off while balance - trailing floor < Y (Y = half the max loss limit: $1,000 on a 50K, $500 on a 25K).
- UP+FLOOR: both.
Grid = 7 sizes x 4 gates = 28 variants + the base (LIT + ATLAS, no lane A).

## Edge scenarios (lane A trades only; LIT / ATLAS untouched)
(a) as measured; (b) half edge; (c) zero edge: every lane A trade's pts shifted by -k x m x risk (m = measured taken mean R at F1,
k = 0.5 / 1.0), worst excursion w1 = min(w1, new pts). So (c) has mean R 0 with the same spread of outcomes.

## Reported per plan x variant x edge
eval pass %, fail %, median days to pass, 6-month slot net $ (owner's payouts - fees at the real prices), net $ / month,
funded blow-up %, p10 of 6-month net, and the change from the base.

## The pick rule (decided now)
A variant is SAFE if under (c) zero edge, on ALL three plans: eval pass % >= base - 1 pt, eval fail % <= base + 2 pts,
funded blow-up % <= base + 3 pts, and 6-month net >= base - one eval fee. Among SAFE variants: the one with the largest summed
6-month net under (a) across the three plans, provided (a) adds > $0 over the base on at least 2 of the 3 plans and (b) does not
lose money over the base on any plan. None qualifies -> "no size is free: lane A stays paper". The pick is a candidate size for
the forward gate's eventual owner card, not a live change. The 51-day caveat stands: one regime, in-sample for lane A.
