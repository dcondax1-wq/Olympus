# night-of-evalplan: for the lead
- Card: card.json -> tools/web_public/business/decisions.json items (id of-lane-a-rollout, recommend later).
- STATE.md line (Order flow section): "night-of-evalplan 2026-11-27 (research/evalplan/PLAN.md): lane A on the 4 MFFU accounts FAILS the
  pre-registered bar (no edge costs $72-$547 per account / 6 mo; all 4 small: real +$5,872, 1/4 edge +$695, zero -$1,097; quiet-days-only
  zero -$229). Newer 20 lane A trades +0.20R vs older +0.79R. Next week = paper forward only; gate 0 = 20 forward trades >= 9 won
  (~Dec 29), stop = <= 2 won of the first 10 or -6R. Then Sim101 -> Zlarior 25K #2 small quiet-days (owner yes) -> rest -> ATLAS funded last."
- Blocker seen: tools/data_pull.py --of asked the PC (request 7ce66b9acc) and waits for its answer (PC answers outside 01:50-16:00 ET);
  the sim used the committed research/orderflow/real_verdict.json rows (51 days). Re-run after new days: sim.py then render.py.
- Needs numba for the sim (tools/blitz25k_lib import via stack_one_account): pip install numba in the cloud.
