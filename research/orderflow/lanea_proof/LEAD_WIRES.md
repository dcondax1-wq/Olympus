# LEAD_WIRES: lane A forward scoreboard (for the lead to wire; helpers don't touch tools/forward_paper.py's wiring)

**What:** each night, `tools/forward_paper.py` prints ONE lane A line and stores the board dict in `research/forward/forward.json`
under `"lanea"`. The gate logic is already written and tested as a pure function: `research/orderflow/lanea_proof/scoreboard.py`
`score(rows, since="2026-11-27") -> dict` (dict keys: taken, skipped, mean_R, PF, net_1, maxdd_R, skipped_mean_R, half1/2_mean_R,
checks, status, line).

**Inputs (rows):** the lane A decision rows of every day from 2026-11-27:
1. preferred: the PC's paper export `data/pc_days/<day>/of/NQ_paper.json.gz` -> `["rows"]` (real-time paper fills, engine/of_paper);
2. fallback when a day has no export: `engine/of_paper.replay_summary(R_today, day, R_prev, prev_day)["rows"]` on that day's summary
   (as `proof.signals` does). Mark such days "replayed" in the board (`b["replayed_days"]`), since their fill is the next bar's open.
Rows are never rewritten. Dedupe by row `id`.

**Costs:** `score` recomputes $ at $1.90 rt (the paper row's usd_1 uses $1.40). R is unchanged.

**The printed line** (example, today):
`Lane A forward (paper, from 2026-11-27): 0 of 30 taken trades yet -> TOO FEW`
later e.g. `Lane A forward (paper, from 2026-11-27): 12 of 30 taken trades, +0.31R avg, PF 1.42, $+410 at 1 micro, max DD 3.1R; skipped 15 at -0.20R -> TOO FEW`

**Gate (pre-registered in DESIGN_lanea_proof.md, frozen):** status PASS only with >= 30 taken AND mean R >= +0.20 AND PF ($) >= 1.30
AND taken > skipped AND both halves (split by day) >= 0R AND max DD <= 6R. Under 30 = TOO FEW, except an early REJECTED once
>= 10 trades and max DD > 6R. At 30+, any check failing = REJECTED -> STRATEGY.md "Tested and rejected".
PASS = an owner card ("lane A on the evals?"), but only after the size re-test (`size.py`) on the forward days too.

**Honest note:** the 51 history days themselves score REJECTED on this gate (40 trades, +0.49R, PF 1.55, but max DD 6.06R > 6R).
The gate is strict on drawdown on purpose. Leave it as written, don't loosen it after the fact.

**Where:** a `lanea_forward(days)` step in forward_paper's nightly run (next to `s1_forward`), the line added to the Brain room
text, and the dict saved. Test: feed `score` the 51 history rows with since="2000-01-01" -> 40 taken, status "REJECTED"
(max DD 6.06R), and since="2026-11-27" -> "TOO FEW".
