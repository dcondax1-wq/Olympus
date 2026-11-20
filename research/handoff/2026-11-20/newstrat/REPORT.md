# newstrat (2026-11-20): ICT ATM + ES/NQ SMT for the Rapid EOD 25K. Result: nothing passed, nothing changed

| What | Result ($250 risk a trade, costs in) |
|---|---|
| 5 pre-registered rule sets (SMT-ATM NQ / MES, session SMT NQ / MES, Judas control) | **0 pass** |
| Best SMT set, session SMT on NQ | Jan-Jun -$39, Jul-Oct -$2,252, 2025 -$3,979 (PF 0.99 / 0.57 / 0.64) |
| ES (MES) instead of NQ | not cleaner: -$1,251 to -$2,698 a period; 10-tick stress -$3.7k to -$10.1k |
| Judas swing control (no ES) | +$1,672 Jan-Jun, then -$2,244 Jul-Oct, -$11,472 2021-25 |
| Rapid EOD 25K eval (60 days) | pass 0-5% for every SMT set, blown 43-86% |
| Correlation with Zlarior / ATLAS | -0.16 to +0.15 (would stack, but no edge to stack) |

What worked: the test itself (rules committed before code; mechanics checked: stops 1 tick worse, 2R targets, win rates
22-43% match the $). The new ATM entry (first close back inside the range) fixed the old R:R problem (more trades clear 1.5R).
What did not: SMT as a trigger has no edge before costs either (gross PF 0.59-1.05). MES has tiny point stops, so real fills hurt
more. Judas = a bare sweep reversal = a lucky half-year.

Money answer for the owner: keep the Rapid EOD 25K on what is already coded (LIT lane + ATLAS lane, `engine/rapid.py`).

Files: `research/newstrat/RULES.md`, `research/newstrat/smt.py`, `research/newstrat/results.json`,
`research/writeups/newstrat-ict-smt-2026-11-20.md`, one line added to `docs/TESTED_AND_REJECTED.md`.
No Decide card (no full pass). No live file, engine file, account or screen touched; no screenshots (no screen changed).
STATE.md left to the lead (one line for "Recently done": "newstrat ICT ATM + SMT: 0 of 5 pass, nothing changed").

Tests: see bottom.
- `python tests/smoke.py`: 7/8 green; test_zenith_mode = `No module named 'playwright'` (container, no screen touched).
- `python tests/run_area.py privacy`: public_build_privacy 59/59 PASS, repo_secrets 12/12 PASS; private_link and phone_safety
  could not start (`No module named 'fastapi'` in this container), not related to these research-only files.
- `python -X utf8 research/newstrat/smt.py` reruns in ~10 s and reproduces every number.
