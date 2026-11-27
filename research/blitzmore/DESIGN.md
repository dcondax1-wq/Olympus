# BLITZ more tests (2026-11-27 night, owner: "BLITZ, I want more tests; all strategies can be better"). Pre-registration

PAPER RESEARCH ONLY: no live file touched. Written and committed BEFORE the first variant run. The only numbers looked at before
writing this are the ones already in research/blitzv2/ (V0 today, V1-V8) and docs/TESTED_AND_REJECTED.md.

Engine: research/blitzv2/blitzv2.py's port of today's rule (parity with engine/blitz.py / tools/blitz25k_lib checked there: 2026 1m 397/397,
2021-26 5m 2,304/2,304; re-checked at the top of results.json). 2026 on 1m bars, 2021-25 on 5m bars (no 1m before 2026), $150 a
trade (>= 1 micro, <= 20), costs in ($1.90 a micro round trip, 1 tick on the entry and on every stop / market exit). +1 tick
sensitivity = one more tick each way ($1.00 a micro). Spans: PICK = 2026 Jan-Jun; CHECK = 2026 Jul-Nov 20 and 2021-11..2025.

Already tested, NOT repeated: V1 noise-area exit, V2 no time exit, V3 cost gate stop >= 0.25% of price, V4 opening-drive checks, V5 limit
at the band, V6 first break only, the 8 exit ideas of blitz-review-2026-11-18 (cuts, band-in, BE at 0.5R), streak SIZE, max 3 a day on the
Rapid (lead only), gap-aware / implied-vol bands, trend-day size, a 10:30 check, "BLITZ when LIT / ATLAS flat" (blitzv2 combined path:
adds nothing, correlation ~0).

## Variants (13, counted; each = today's rule with ONE change; M13 is the only combination)
- M1  max 3 trades a day (today 6)
- M2  pause for the day after 2 losing trades in a row that day
- M3  no entry after 14:30 ET (last check 14:30; today 15:30)
- M4  morning only: checks 11:00-12:30 (no entry after 12:30)
- M5  afternoon only: checks 13:00-15:30
- M6  daily-trend aligned: long only when the prior RTH close is above the mean of the last 20 prior RTH closes, short only when below
- M7  VIX regime: trade only when the PRIOR day's VIX close >= 18 (data/VIX_1d.csv)
- M8  stop-size cap: skip when the 1.5 x ATR5 stop is > 0.40% of price (the mirror of the V3 cost gate, which kept only wide stops)
- M9  tighter stop: 1.0 x ATR5 (today 1.5)
- M10 wider stop: 2.0 x ATR5
- M11 fixed target 2R (today none: the 1.5R trail after +1R, out after 30 min)
- M12 time exit after 60 minutes (today 30; V2 removed it entirely, 60 was not tried)
- M13 combination of every single variant M1-M12 that survives the PICK and CHECK rules below (defined after, counted as a test)
Everything else = today's rule (prior-range filter >= 0.8, 14-day band, 10 checks, trail 1.5R after +1R, 6 a day, -3R day stop, flat 15:55).

## Scores (per span: 2026 Jan-Jun, 2026 Jul-Nov 20, 2021-25; and each year 2022-25)
trades / week, win %, PF, net $, $ / month, max DD, Builder 25K / Rapid EOD 25K / 50K 40-session pass / fail / median sessions to pass (daily
level at $150 a trade via research/moretrades span_stats), +1 tick PF and $ / month, walk-forward vs today (6-month windows every 3 months).
Significance: sign-flip permutation test (20,000 flips, one-sided) of the mean DAILY $ difference variant - today on ALL sessions
2021-11..2026-11 (the same trades for a pure filter = the removed trades' $), Holm-corrected over the 13 tests at alpha 0.05.

## Rules fixed now
- PICK: a variant is picked on 2026 Jan-Jun only if its $ / month beats today's AND its PF >= today's PF - 0.05.
- CHECK (both must hold): 2026 Jul-Nov 20 $ / month >= today's, AND 2021-25 $ / month >= today's.
- "Holds up in 2021-25" (the owner's question) = PICK + CHECK + 2021-25 PF >= 1.15 AND 2021-25 PF with +1 tick > 1.05 AND every year 2022-25 $ >= 0 AND Holm p <= 0.05.
- A variant that only improves 2021-25 while losing > 25% of today's 2026 $ / month is reported as a regime trade-off, not a win.
- No variant clears it -> plain verdict "nothing makes 2021-25 hold up", with the best 2021-25 number and what it cost in 2026.
- A card to the owner needs the "holds up" rule AND 25K / 50K pass not lower and fail not higher in both 2026 spans.
