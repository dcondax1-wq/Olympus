# BLITZ pillar test: pre-registered design (written 2026-11-24 ~00:30 ET, BEFORE any scored run)

Paper research only. Nothing live changes, nothing is armed, live_model*.json untouched.

## Engine (reused, not new)
research/onebook/book.py -> research/plans/rank.py (real fills: ATLAS 10 ticks a side, LIT as stored, BLITZ as stored
1-tick fills, $1.90 a micro, soft-day cuts, MFFU Rapid news window, 30% best-day guard on the Rapid eval).
Account: MFFU Rapid EOD 25K ($97.20). Eval: 2,000 paths x 60 sessions (seed 7). Slot: 1,000 paths x 126 sessions (seed 23).
Spans: H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct, REF = 2021-11..2025 (BLITZ 5m bars there).

## Variants (6 counted, + V0 baseline)
- V0  today: LIT + ATLAS, eval and funded.
- V1  the BUILT lane (engine/rapid_blitz.py): + BLITZ $300 / 30% of room in the EVAL only; one position on the account
      (a BLITZ trade overlapping any LIT or ATLAS trade is dropped). Funded = LIT + ATLAS.
- V1r V1 without the one-position drop (engine default; reference only, not eligible).
- V2  V1 + no BLITZ entry from a LIT entry until 30 min after that LIT trade's exit (live-implementable).
- V2b V1 + no BLITZ entry within 30 min before OR after a LIT trade (uses the future LIT entry: diagnostic ceiling, not eligible).
- V3  V1 + BLITZ at half size once the day's closed $ (all lanes) is >= 50% of the best-day cap (30% x $1,500 x 0.95).
- V4  V1 + BLITZ stops for the day after its first losing trade (no BLITZ entry after that loser's exit).
- V5  V1 with BLITZ at $150 instead of $300.
Own lane: BLITZ alone on a Rapid 25K (eval + funded, $300 / 30% room), and BLITZ fixed-$ stats at $150 / $300 (no account rules).

## Pick rule (fixed now)
Eligible: H1 eval fail <= V0 H1 fail + 1.0 point. Among eligible V2, V3, V4, V5: the highest H1 eval pass %, ties -> H1 slot net.
The pick is "worth a card" only if ALSO: H2 eval fail <= V0 H2 fail + 1.0, H2 slot net >= V0, H1 slot net >= V0,
REF slot net >= V0 REF - $100 (6 months). V1 itself is judged by the same checks.
Multiple testing: 4 eligible variants x 3 spans. Paths are resamples of the SAME ~125 / 78 / 1,077 sessions, so more paths
do not add data; a fail-rate gap under ~1 point in H1/H2 is treated as noise.
