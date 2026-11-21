# Holidays / roll / FOMC (2026-11-21): pre-registered design, committed BEFORE any run

Question (lead): for LIT and ATLAS separately, how did they trade in (a) Thanksgiving weeks, (b) roll weeks, (c) Dec 15 - Jan 5,
(d) FOMC days vs normal days, and does "sit out" or "half size" in any of them beat trading through? Research only.
Code research/holidays/holidays.py -> research/holidays/results.json; write-up research/writeups/holidays-2026-11-21.md.

## Already tested (docs/TESTED_AND_REJECTED.md) - not redone, referenced
- LIT (S2 edge 2026-11-15): holiday-thin days (holiday Globex sessions, the day before / after, early closes, Dec 24 - Jan 2;
  x0.5 / x0.75 / skip) and the contract roll window (5 sessions before the switch to the last trading day; x0.75 / x0.5 /
  skip): rejected. => LIT (b) roll week is NOT re-run as a rule (shown descriptively only).
- ATLAS: flat 3 min before CPI / jobs / FOMC: rejected (-$82 a month Jul-Oct). Whole-day FOMC rules for ATLAS: new.
- LIT news: "Tier-1 news day: only setups after the release": rejected. Whole-day FOMC sit-out / half for LIT: new.

## Windows (fixed; trading days = the sessions the bots trade, ET dates)
(a) Thanksgiving week: Mon-Fri of the week of the 4th Thursday of November.
(b) Roll week: Mon-Fri of the week holding the CME roll date (8 calendar days before the 3rd Friday of Mar / Jun / Sep / Dec,
    the date the bot's code rolls, e.g. 2026-12-10).
(c) Holiday stretch: Dec 15 - Jan 5 inclusive.
(d) FOMC days: the dates of "FOMC rate decision" in data/news/events.csv.
Normal = every other session.

## Data / money
LIT: the 631 stored live trades (tools/account4_sim, 1m fills 2026, 5m 2021-25). ATLAS: the live account stream
(tools/atlas_health.stream). Costs in. Fixed view: LIT $350, ATLAS $250 a trade (research/regime_guard/guard.py tusd).
Periods: 2026 Jan-Jun, 2026 Jul-Oct 16, 2021-11..2025-12.
Descriptive per window vs normal: trades, PF, $ a trade, worst day, share of traded days with a day loss >= $600.
Accounts (research/regime_guard/guard.py, same engines): LIT Builder 50K eval (live two_week sizing, 600 paths, 60 sessions,
half = risk x2 on the sizer, out = removed); ATLAS funded Builder 25K Monte Carlo from today's account engine of
tools/atlas_health.score (600 paths, live stuck stop).

## Rules (16 versions): each window x {sit out, half size} x {LIT, ATLAS}; LIT x roll week not run (already rejected).
## Pass bar (per bot, per version), ALL of:
1. the window has trades in 2026 Jan-Jun AND 2026 Jul-Oct AND 2021-25 (else: untestable in 2026 -> cannot pass; said plainly);
2. fixed $: net higher in each of the three periods;
3. accounts: LIT eval 60-session pass not lower by > 2 points and fail not higher in any period; ATLAS funded lost in 6 months
   not higher and $ a month not lower by > $10 in any period;
4. trades a week >= 2.0 in both 2026 halves.
A Decide card only for a full pass. Thanksgiving week and Dec 15 - Jan 5 have no 2026 sample (data ends 2026-11-19): by rule 1
they can only be described, never adopted, from this test. Their 2021-25 numbers are reported as information.
