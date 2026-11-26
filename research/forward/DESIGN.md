# Forward-paper harness: pre-registered rules (written 2026-11-26 BEFORE the first forward run; not changed after results)

Why: ideas keep dying in backtests or sitting as "paper lead / watch" lines in docs/TESTED_AND_REJECTED.md with nobody
checking them on NEW days. This harness scores each watched rule on sessions it has never seen, against its OWN backtest
band, so a lead can graduate (-> an owner yes/no card, never live by itself) or be dropped. PAPER RESEARCH ONLY.
Code: `tools/forward_paper.py`. Output: `research/forward/forward.json` (state), `bands.json` (each rule's frozen backtest
band), `journal.jsonl` (one line per rule per ISO week).

## The unit every rule is scored in: R per event, costs in
- **standalone** rule (its own trades): the trade's net R (points after the cost model / stop distance).
- **skip** filter on a live-twin bot: event = a twin trade the rule would skip; value = -(that trade's net R)
  (positive when the skip avoided a loss).
- **size** rule x m on a live-twin bot: event = a twin trade the rule resizes; value = (m - 1) x net R.
Live twin on new days = `tools/livegap.lit_twin` / `atlas_twin` (the backtest engine re-run on the PC's bars).
Backtest band = the SAME function on the study's backtest trades (the stored LIT / ATLAS backtests for filters).

## Forward window
Each rule has `fwd_from` = the first session AFTER the last bar its study used (all seeds: data to 2026-11-20 -> forward from
2026-11-23). Sessions between a band's end and `fwd_from` count for neither.

## Band, z and the bars (fixed here)
Band: mean R `mu`, standard deviation `sd`, `n_bt` of the rule's backtest events. Forward: `n`, mean `m`, sum, days in.
z = (m - mu) / (sd / sqrt(n)).
- **PROMOTE** (status `promote`: the lead writes an owner yes/no card with the full CLAUDE.md proof, incl. eval pass/fail):
  n >= 20 AND z >= -1.0 (inside or above the band) AND forward sum > 0.
- **DEMOTE** (status `demoted`, stays scored but flagged dead): (n >= 10 AND z <= -2.0) OR forward sum <= -8 R.
- otherwise `watching` (n < 20 or between the bars). A rule with an error keeps its last state and shows `error`.
Promotion never changes anything live; size-up rules still need the eval check (leverage is not an edge).

## Seed rules (from TESTED_AND_REJECTED rows marked paper / watch, 2026-11-26)
| id | kind | bot | rule | source |
|---|---|---|---|---|
| ict_ote_dol | standalone | - | ICT OTE 70.5% of the 09:30-10:00 leg, only when the PDH/PDL draw agrees (ICT lab G3) | ict-lab-2026-11-25 |
| ict_mmbm_week | standalone | - | MMBM / MMSM, only with the weekly bias (prior week close vs its mid) | ict-lab2-2026-11-25 |
| atlas_skip_news | skip | ATLAS | skip ATLAS on Tier-1 days (FOMC, CPI, PPI, NFP: events.csv high) | news-playbook-2026-11-26 |
| atlas_half_off_sb | size x0.5 | ATLAS | ATLAS x0.5 outside Silver Bullet hours (03, 10, 14 ET hour) | owner card atlas-sb-half |
| blitz_v1_noise | standalone | BLITZ | BLITZ V1 noise-area exit (band / VWAP, no clock, no trail), 5m | blitz-v2-2026-11-26 |
| lit_second_after_stop | standalone | LIT | LIT L11: a 2nd trade the same day only after a STOP (the extra trades) | more-trades-2026-11-25 |
| lit_x15_extreme | size x1.5 | LIT | LIT x1.5 when the entry is in the bottom/top 20% of the day's range on its side ("at the extreme") | structure-2026-11-24 F3 |
| ideamill:<id> | standalone | - | every idea mill idea that reaches its paper gate (G3 / D / confirm), auto-added | ideamill DESIGN_v3 |
