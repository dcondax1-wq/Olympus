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
- VIX / VXN: not used by any of the 5 rule sets (lead's 11:13 UTC data note checked), so the fresh CBOE files change nothing.

# Round 2 (lead): regime guard. Result: nothing passed, nothing changed

| What | Result |
|---|---|
| 4 pre-registered pre-session signals x half / sit out (8 versions) | **0 pass** |
| Do they tell 2021-25 days from 2026 days? | No: "bad" days are as common or more common in 2026 (G1 flags 65% of Jul-Oct) |
| LIT in a 2021-25 market | guard turns +$2,065 into -$1,801..-$5,933 (LIT's old-year profit sits on the flagged days) |
| ATLAS funded 25K lost in 6 months, 2021-25 market | 94.5% -> best 85.7% (G3 sit out), which costs $70-105 a month funded in 2026 |
| Post-hoc lead | ATLAS trades worse on chop days in all 3 periods (ZEUS Lab paper candidate, not a switch) |

Baseline check: the no-guard ATLAS funded row reproduces atlas-health-2026-11-18 exactly (8.5 / 9.2 / 94.5% lost).
Fresh VIX (lead's pc merge, to Nov 19) used. Files: `research/regime_guard/`, `research/writeups/regime-guard-2026-11-20.md`,
+1 line docs/TESTED_AND_REJECTED.md. No Decide card. LEAD_WIRES: still none.

# Round 3 (lead): skeptic check of today's passing card + Rapid spot check

| Card | Verdict | Numbers (10 ticks, today's funded 25K, $ a month / lost in 6 months) |
|---|---|---|
| atlas-funded-streak-1micro | **WEAKER THAN CLAIMED** | Reproduced exactly (H1 $503/17.6% -> $481/12.2%, H2 $402/21.7% -> $408/10.9%). Holds on 2 more seeds. Day-shuffled paths: H2 $372/23.5% -> $319/18.5% (-$53). Jan-Jun-like: flat room 40% beats it ($527/11.0%). With room 40%: H2 14.0% -> 7.7% at $0, H1 -$49 |
| rapid25-lit-bank | **NO HOLDS** | pre-registered 1-pt eval-fail limit broken (H1 0.5 -> 3.1%); close call (+$24/+$101) |
| atlas-on-rapid | **YES HOLDS** | $1,883 vs $221, $800 vs $191; no payout 7.4 vs 55%, 15.1 vs 50% |

Code read: no look-ahead, same trades / costs / paths in both arms, floor math untouched. Live build must copy: streak updated
at session end; a breakeven scratch (-$3.80) counts as a loss. Neighbours: not a knife edge (2 -> 2 micros, 3 -> 1 micro close).
Card text edited in tools/web_public/business/decisions.json (risk + recommend_why; recommend stays yes; $ unchanged);
test_decide 14/14. Write-up research/writeups/skeptic-atlas-streak-2026-11-20.md, code research/skeptic/streak.py.
Installed numba in this container (pip, free) to run the card's own tool.
Screenshot: NOT taken (the local page server + browser step was refused in this container) - lead: one 390x844 @2 shot of
business/plan.html with the streak card open, text-only change.

# Round 4 (lead): skeptic of the live patches + card rapid-atlas-size-10t

| Item | Verdict |
|---|---|
| card rapid-atlas-size-10t | **HOLDS** (lost Rapids down on week blocks, day blocks and another seed; -$31..38 / -$93..141 a month; $500-pause days -> 0) |
| atlasedge account_b.patch, switch ON | **FIX FIRST**: FUNDED_ON also reaches a funded combo 50K via combo50k.ab_spec -> scope the default to plan builder25k (one line in the write-up). Otherwise never larger (3,168 states), eval untouched, Rapid untouched, restart-safe |
| day-rapid engine/rapid.py atlas_slip patch | **SAFE** |
Write-up research/writeups/skeptic-live-patches-2026-11-20.md.
