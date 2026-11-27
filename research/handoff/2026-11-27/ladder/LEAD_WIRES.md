# night-of-ladder: for the lead (branch includes night-of-evalplan's 2 commits)
- NEW tools/of_ladder.py: scores the lane A gate ladder (research/evalplan/PLAN.md section 3) -> research/evalplan/ladder.json.
  Forward rows from 2026-11-27: PC shipped paper days (data/pc_days/<day>/of/NQ_paper.json.gz) first, else real_verdict.json replay
  rows. E5: a row's R_e5 (or fill_e5 vs fill + stop + d) is judged as the WORSE of the two fills. Stops are sticky.
- Gate 0 is judged ONCE on the first 20 forward trades (>= 9 won and $ > 0); stop earlier at <= 2 won of the first 10 or sum <= -6R.
- Step 1 reads data/of_ladder_sim.json (absent until you build the Sim101 route): rows with fill_gap_ticks, hedge_conflict /
  one_position_conflict, R, usd_1, taken, day.
- Card: research/evalplan/card_gate.json exists ONLY while a gate is passed and not stopped (id of-ladder-step<N>); wire it into
  tools/web_public/business/decisions.json when it appears. Step 1 card = no money, recommend yes; step 2+ = money, recommend later.
- Hooks (soft, try/except): tools/forward_paper.run -> of_ladder.run (doc["of_ladder"]); tools/build_brain_learn.learning() adds one
  "ideas on trial" row id of_lane_a_ladder (no page edit needed). brain/learn.json rebuilt.
- tests.test_of_ladder (nq area, run_area.py). research/evalplan/sim.py: numba-free fallback (stub njit) when numba is missing.
