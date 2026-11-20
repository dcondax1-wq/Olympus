---
tags:
  - zeus/research
  - family/risk
  - verdict/finding
  - lane/rapid
type: "research"
date: "2026-11-20"
status: "finding - no live change. Rules match MFFU (0 gaps that cost money). Keep LIT + ATLAS $250 as built (atlas-on-rapid stays YES). rapid25-lit-bank flips YES -> NO at real fills (eval fail 0.5 -> 3.1% ..."
source: "research/writeups/rapid-launch-2026-11-20.md"
aliases:
  - "Rapid EOD 25K launch check"
---

# Rapid EOD 25K launch check

> [!info] Verdict: finding
> finding - no live change. Rules match MFFU (0 gaps that cost money). Keep LIT + ATLAS $250 as built (atlas-on-rapid stays YES). rapid25-lit-bank flips YES -> NO at real fills (eval fail 0.5 -> 3.1% Jan-Jun-like, over the pre-set 1-point limit). New optional card: size ATLAS's Rapid lane on a 10-tick stop (fewer accounts lost, -$31 to -$141 a month); patch in the lead's wires.

**Full title:** Rapid EOD 25K launch check - MFFU rules vs the code, what it trades at real fills, sizing vs the $500 DLL, payout path

## Summary

MFFU's help center (read 2026-11-20) = the code for the Rapid EOD 25K with DLL - $1,500 target, $1,000 EOD trailing floor locking at +$100, DLL $500 = a soft pause (resets 6 PM ET; the bot's day also starts 18:00 ET), 2 minis / 20 micros, 30% best day in the eval only, 4 days, Tier-1 news banned funded only (-2/+2 min; bot -3/+2.5), daily payouts above $1,100, $250 since the last, $500 minimum, 90%, 7-day inactivity. At ATLAS's real fills (10 ticks a side), LIT + ATLAS makes $1,883 / $800 a month (Jan-Jun / Jul-Oct-like; -$50 2021-25-like) vs LIT alone $221 / $191 and ATLAS alone $707 / $141. Eval passes in 80-86% of runs within 60 trading days, median 33 / 26 days; first payout median Feb 10 / Feb 18 2027 (middle half Jan 20-Mar 16 / Jan 22-Apr 13); 12% / 26% of runs lose the first Rapid before any payout; 6 months pays $11,428 / $4,945 before fees. A full ATLAS stop at real fills overshoots its sized $ by up to ~36% (tight stops, many micros): days under -$500 1.1 per 100 traded days Jan-Jun-like -> MFFU's soft pause (never a fail). Sizing on a 10-tick stop makes that 0 and cuts the funded loss 27.2 -> 24.0% / 38.0 -> 34.5% for -$141 / -$31 a month.

## Links

- Family: [[Family risk]]
- Day: [[Day 2026-11-20]]
- Strategies: [[Rapid lanes]]
- Runs: `tools/money/rapid25_launch.py run / sizing -> research/lab/rapid25_launch.json; design research/second/rapid25_launch_design.md (committed 4139ee46 before any run); tests/test_rapid_launch.py`
- Source: `research/writeups/rapid-launch-2026-11-20.md`
- Back to [[ZEUS Home]]
