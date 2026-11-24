# Do the time windows add money? Pre-registration (written 2026-11-24 BEFORE any number below was computed)

PAPER RESEARCH ONLY. Owner: "tuning it to work on certain times is bad". Code `research/notime/notime.py` -> `results.json`;
write-up `research/writeups/notime-2026-11-24.md`. Costs in everywhere; futures data only.

Variants (same rules otherwise; one position at a time; flat 15:55 = the MFFU 16:10 close kept; CME 17:00-18:00 halt kept):
- **LIT**: today (entries 02:00-15:30, run `lit_hours_base` = lit_live) vs **no window** = entries 18:00-15:30 on the whole
  trading day, one trade a day (stored run `lit_hours_full`, engine/lit all_hours, built 2026-10-18) vs **late** = entries to
  15:50 (`lit_hours_late`). These runs already exist; reported now on 2021-25 too (the Oct 18 study judged 2026 only).
- **ATLAS members** (live code engine/second.run, replayed month by month 2021-11 .. 2026-10-16; 5m execution before 2026):
  EMA (today: 03:00-09:30, no Mondays) vs "day" (02:00-15:30, no Mondays) vs "any" (00:00-15:55, Mondays allowed);
  MACD (today: 02:00-05:00 + 09:30-11:00) vs "day" (02:00-15:30) vs "any" (18:00-24:00 + 00:00-15:55);
  S/R (today: 09:30-12:00) vs "day" (02:00-15:30) vs "any" (00:00-15:55). Members alone at their own $500 size.
- **BLITZ**: not run. Its anchor (the 09:30 RTH open and its noise band) IS the strategy; there is no time-free version.
Spans: 2021-25, Jan-Jun 2026, Jul-Oct 2026. Report: trades/week, PF, net $, $/month, max DD, daily-level Builder 50K / 25K
(x0.5) / Rapid EOD 25K (x0.5) 40-session pass / fail (rules of research/portfolio/portfolio.evals).
Verdict per strategy: "the window ADDS money" when today beats the no-window version on net $ in at least 2 of the 3 spans
AND on the sum of the 3; "the window costs money" when the no-window version wins on the same test; else "no clear answer".
Plus a table of every live rule tagged TIME (clock / weekday / calendar) vs STRUCTURE (price / level / volatility).
