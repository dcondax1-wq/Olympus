# Rapid EOD 25K eval-only LIT target: pre-registered design (written 2026-11-24 ~09:25 ET, BEFORE any scored run)

Paper research only. Nothing live changes, nothing is armed, live_model*.json untouched.
Follow-up to research/writeups/stops-targets-time-2026-11-24.md (lead #5).

## Engine (reused, not new)
research/pillars/blitz_rapid.py -> research/onebook/book.py -> research/plans/rank.py: LIT + ATLAS on ONE MFFU Rapid EOD 25K
($97.20), real fills (ATLAS 10 ticks a side, LIT as stored), $1.90 a micro, the 30% best-day guard + 4 days on the eval,
the Rapid news window on the funded account. Eval 2,000 paths x 60 sessions (seed 7); slot (eval + funded, 6 months)
1,000 paths x 126 sessions (seed 23). Spans H1 = 2026 Jan-Jun, H2 = 2026 Jul-Oct, REF = 2021-11..2025.

## Variants (2 counted, + V0 baseline = today's pillar row "V0 today LIT+ATLAS")
- T15: in the EVAL only, every LIT trade exits at a fixed 1.5R target (live stop, same BE at +1R, same 15-min
  check; re-walked by tools/stops_targets_time.units({"tgt": "R1.5"}), which reproduces the live exits with options off).
  Funded keeps the VIX band. ATLAS unchanged.
- T20: the same with 2R.

## Pass rule (fixed now)
A variant is "worth a card" only if ALL hold: H1 AND H2 eval pass % above V0 with eval fail <= V0 + 1.0 point;
H1 AND H2 slot $/month >= V0; REF slot net >= V0 REF - $100 (6 months). Report pass %, fail %, median days to pass, $/month.
Multiple testing: 2 variants (21 with the 19 of the parent test); paths resample the same sessions, so a gap under ~1 point
is noise.
