# Forward-paper harness (2026-11-26, big-forward)

Ideas used to die in backtests or sit as "paper lead / watch" lines nobody re-checked. `tools/forward_paper.py` now scores each
watched lead every night on sessions it has never seen, against its OWN backtest band. PAPER ONLY: it never trades, sizes, arms
or edits a live file (live_model*.json hashed before / after). Rules + bars written first: `research/forward/DESIGN.md`.

| Rule | Kind | Backtest band (R a trade x n, 2021-11..2026-11-20) | Forward (from 2026-11-23) |
|---|---|---|---|
| ict_ote_dol: OTE + PDH/PDL draw gate | standalone | +0.17R x 240 | starts with the next pulled session |
| ict_mmbm_week: MMBM + weekly bias | standalone | +0.22R x 92 | " |
| atlas_skip_news: ATLAS off Tier-1 days | skip (value = -R skipped) | +0.10R x 100 | " |
| atlas_half_off_sb: ATLAS x0.5 outside SB hours | size | +0.03R x 687 | " |
| blitz_v1_noise: BLITZ V1 noise-area exit | standalone | +0.15R x 1,059 | " (needs numba) |
| lit_second_after_stop: LIT L11 extra trades | standalone | -0.01R x 64 | " |
| lit_x15_extreme: LIT x1.5 at the day's extreme | size (+0.5R x R) | +0.27R x 118 | " |
| ideamill:<id> | standalone, auto | each idea at the mill's paper gate | none today (0 at G3/D) |

Bars (pre-registered): PROMOTE = n >= 20 forward events, z >= -1 vs the band, forward sum > 0 -> the lead writes an owner yes/no
card with the full CLAUDE.md proof (size-ups still need the eval check). DEMOTE = n >= 10 and z <= -2, or forward sum <= -8R.
Check run with a pretend start of 2026-10-19 (25 sessions): every rule produced events (OTE 3, MMBM 1, news 5, SB 11, BLITZ 36,
L11 1, extreme 4), none near a bar yet. At ~1 event a week some rules need ~5 months to reach 20: that is the honest speed.

Run: `python -X utf8 tools/forward_paper.py` (15-25 s; `--bands` recomputes bands, `--report` prints the table). Nightly: the
`forward` step of `tools/learn_night.py` (after blitz; `--skip forward` to leave it out). Out: research/forward/forward.json,
bands.json, journal.jsonl (one line per rule per ISO week). Test: `python -X utf8 -m tests.test_forward_paper` (area nq).
Adding a rule = one pure function `fn(a, z) -> [ev(day, t, R)]` + one RULES entry + a DESIGN.md row written before its first run.
