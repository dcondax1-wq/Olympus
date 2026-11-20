---
tags:
  - zeus/research
  - family/other
  - verdict/research
  - bot/atlas
  - bot/blitz
type: "research"
date: "2026-11-04"
status: "nothing to switch on. ATLAS's funded pay is capped by MFFU's 5-payout rule, not by size or targets; no funded-phase knob moves it; the only thing that does is more trades from a second window (the ..."
source: "research/writeups/2026-11-04_atlas_round3.md"
aliases:
  - "ATLAS round 3"
---

# ATLAS round 3

> [!abstract] Verdict: research
> nothing to switch on. ATLAS's funded pay is capped by MFFU's 5-payout rule, not by size or targets; no funded-phase knob moves it; the only thing that does is more trades from a second window (the stop-hunt members at half size), which is already running as a paper shadow. BLITZ funded: corrected to $322 / $82 a month; one fix to test lifts it to $357 / $218.

**Full title:** ATLAS round 3 - why the funded 25K pays about $580 a month and what could raise it (39 versions), plus the BLITZ funded fix

## Summary

Job 30. The owner's ATLAS 25K passes its eval often (2-week pass / fail 65.5 / 0.0 and 43.5 / 0.0) but the funded account pays only $586 / $519 a month (6-month Monte Carlo, to you, 80% split). 39 versions on the same ATLAS trades - funded sizing, ask line, winner cap, day take-profit, trades a day, a consistency-aware cap, partial exits, member target banking, and a second entry window (the stop-hunt members). Judged on 2026 only - Jan-Jun pick, Jul-Oct check - and, because the eval is unchanged by any funded-phase knob, with the eval's pass / fail beside every row. Then the BLITZ funded-only verdict in plain words and one fix.

## Links

- Family: [[Family other]]
- Day: [[Day 2026-11-04]]
- Strategies: [[ATLAS]], [[BLITZ (paper)]]
- Refers to: [[2026-11-04_lit_ideas_round3|LIT ideas round 3]]
- Runs: `ar3_funded_today, ar3_funded_max_trades_day_3, ar3_funded_size_60pct_max1000, ar3_funded_half_off_at_10R, ar3_funded_winner_cap_600, ar3_units_hunts_x05, ar3_units_hunt_trend_x05, ar3_units_hunt_asia_x05, ar3_units_sr_vix_bank5, ar3_units_ema_3R, ar3_combo_hunt_trend_x05_day_tp5000`
- Source: `research/writeups/2026-11-04_atlas_round3.md`
- Back to [[ZEUS Home]]
