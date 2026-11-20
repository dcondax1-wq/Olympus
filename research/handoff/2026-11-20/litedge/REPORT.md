# day-litedge REPORT (2026-11-20): more money from Zlarior (LIT)

**Result: 0 of 5 new ideas pass. Zlarior stays exactly as it is. No Decide card. Nothing live touched.**
Write-up: `research/writeups/lit-edge-2026-11-20.md`. Rules fixed before the run: `research/lit/litedge_design_2026-11-20.md`
(committed first, 5588e419).

| What | Jan-Jun $/mo | Jul-Oct $/mo | 2021-25 $/mo | Result |
|---|---:|---:|---:|---|
| Today (live Zlarior, LIT size, costs in) | $5,562 | $2,670 | $25 | - |
| (a) Limit 2 ticks better than the fill | $5,184 | $2,585 | $26 | No: misses runners |
| (b) Skip setups 60+ min after the sweep | $849 | $824 | $119 | No: the late ones are the money |
| (d) Big-news days: profit at 4R | $4,997 | $2,616 | $89 | No |
| (e) ES instead of NQ when ES has 25%+ more room | $5,069 | **$9,656** | $198 | No (loses the pick half); paper lead |
| (f) No breakeven in the first 10 min | $5,068 | $2,670 | $25 | No |
| Cost stress +10 ticks a trade | $5,176 | $2,447 | -$353 | Still positive in 2026 |
| Cold run (7 twin trades, -$858, -4.2R) | - | - | - | Normal: 8.8% of 2026 7-trade windows as bad |

## What worked
- Nothing as a rule. The nearest: trade MES instead of MNQ when ES's own sweep offers a target 25%+ bigger in R. Jul-Oct
  +$25.9k at the LIT size (23 ES trades, 6 targets), 2025 +$8.8k, eval 2-week pass 39.1 -> 55.1% in Jul-Oct, but Jan-Jun
  -$3.0k (35 ES trades, 1 target) and eval -$10.6k: fails G1/G2. Second ES switch in two days with this shape
  (2026-11-19 smt_pick). Worth tracking forward on Nov-Dec 2026 data; not a live change.
- Answers the owner asked for: limits at a retrace (10-50% of the risk) fill 0-60% and throw away $17-34k of Jan-Jun
  winners for $600-2,200 better price: keep the market order. The cold run is ordinary variance; all 7 had wide stops
  (42-68 pts), so the size rule kept them small (1-4 micros).

## What did not
- All 5 pre-registered ideas (table above). (c) bias and the rest of (d) news were not re-run: every input listed was
  already rejected (sources in the write-up). "ATM model ICT": no codable definition, not tested.

## Files
- `tools/research/litedge.py` (check / run / study; reuses tools/lit_more_money scoring; `check`: 631 trades, 0 differ)
- `research/lit/litedge.json` (ideas + stress), `research/lit/litedge_study.json` (fill map, timing map, cold run)
- `research/lit/litedge_design_2026-11-20.md`, `research/writeups/lit-edge-2026-11-20.md`

## Tests
- `python tests/smoke.py`: 7/8 green; `tests.test_zenith_mode` fails with `No module named 'playwright'` (Python
  playwright not installed in this container; unrelated to this work, no screen touched).
- `python -X utf8 tools/research/litedge.py check`: 631 trades, 0 differ from the live trades.
- `python -m tests.test_lit_live`: stopped by my 15-minute timeout at 2026-07-02 (6,496 polls). It showed 29 differences,
  first seen between 2026-04-01 and 2026-05-12. This branch changes no engine / live file (`git diff` on engine/,
  server.py, live_model*.json is empty), so the differences were already on pc. Lead: worth one full run on pc.
- `python tests/run_area.py privacy`: repo_secrets 12/12 and public_build_privacy pass; private_link and phone_safety
  can't start here (`No module named 'fastapi'`, missing from this container).

## VIX data (lead's note, 11:14 UTC)
Re-ran the cold-run study with pc's fresh data/VIX_1d.csv + VXN_1d.csv (to Nov 19) and the candidate cache rebuilt:
**no number moved** (same 7 twin trades, same exits, -$858 / -4.18R). Why: none of the 7 hit a target (stops, BE,
a cut, an end-of-day exit), and no setup was added or dropped by the band. The idea scores (Jan-Jun / Jul-Oct /
2021-25) use trades up to Oct 16 only, where the old file was complete, so they do not change either. The VIX files
were put back to this branch's copy (pc already has the fresh ones).

## Screenshots
None: no screen changed.
