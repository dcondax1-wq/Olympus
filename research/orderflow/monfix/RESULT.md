# Lane A: the Monday "previous day" fix (night-of-monfix, 2026-11-27)

Paper research only. No live or paper rule changes except which file counts as the previous day (a bug fix).

## The bug (found by the of-v5 levels/combo reviews)

- `research/orderflow/of_battery.levels` and `engine/of_paper._prev_summary` took the calendar file before a Monday as its
  "previous day". That is the Sunday-evening file (Globex only, no 09:30-16:00 bars), so **7 of 9 Mondays had no prior-day
  high/low (pdh/pdl)**.
- On 10-05 and 10-12 the Sunday file was thin (< 50,000 rows) and dropped, so the code fell back to Friday, but **Sunday 18:00-24:00
  was lost from the overnight high/low** (onh 31,221 vs 31,099 on 10-05; 31,289 vs 31,260 on 10-12).

## The fix

- The previous day = the last file **with RTH bars**, within 4 calendar days.
- A Globex-only file in between (any size) adds all its bars to the overnight range. The overnight still starts at the prior RTH
  day's 18:00 (unchanged: lane A's Globex window), so a normal Tuesday is unchanged.
- If no RTH day is in reach (the data starts on a Sunday), the Globex file still feeds the overnight.
- Live: `_prev_summary` returns the RTH day plus `R["extra"]` (the Globex files), and `step()` puts them in the levels' day set.
- The of_battery run keeps thin files in `D` (for levels only). LIT/ATLAS rows on them are still skipped.

## Before vs after on the real days

43 trading days (2026-09-28 to 11-25, weekdays with RTH; the 11-26 half day and 9 Sunday files skipped) = 8.6 weeks.
Costs in. $ at 1 micro. v1 = next open + 1 tick ($1.40). E5 = limit at the level for 5 min, then market +18 ticks ($1.90).
Halves = mean R, older / newer half of the days.

| book | entry | trades | /week | win % | mean R | PF ($) | $ 1 micro | max DD | halves R |
|---|---|---|---|---|---|---|---|---|---|
| first of day, BEFORE | v1 | 39 | 4.5 | 48.7 | +0.46 | 1.55 | +$1,550 | $1,093 | +0.79 / +0.10 |
| first of day, AFTER | v1 | 39 | 4.5 | 46.2 | +0.38 | 1.41 | +$1,212 | $1,331 | +0.80 / -0.06 |
| first of day, BEFORE | E5 | 39 | 4.5 | 53.8 | +0.59 | 2.62 | +$3,223 | $358 | +0.90 / +0.26 |
| first of day, AFTER | E5 | 39 | 4.5 | 51.3 | +0.51 | 2.40 | +$2,931 | $542 | +0.91 / +0.10 |
| one at a time, BEFORE | v1 | 61 | 7.1 | 41.0 | +0.18 | 1.14 | +$683 | $821 | +0.30 / +0.06 |
| one at a time, AFTER | v1 | 64 | 7.4 | 39.1 | +0.12 | 1.07 | +$378 | $998 | +0.26 / -0.01 |
| one at a time, BEFORE | E5 | 62 | 7.2 | 50.0 | +0.47 | 1.70 | +$2,812 | $1,163 | +0.58 / +0.34 |
| one at a time, AFTER | E5 | 65 | 7.6 | 47.7 | +0.40 | 1.53 | +$2,370 | $1,163 | +0.54 / +0.25 |
| later-in-day only, AFTER | v1 | 25 | 2.9 | 28.0 | -0.28 | 0.63 | -$834 | $1,195 | -0.64 / +0.06 |
| later-in-day only, AFTER | E5 | 26 | 3.0 | 42.3 | +0.23 | 0.76 | -$561 | $1,272 | +0.01 / +0.50 |

## Plain answer

- **The fix makes lane A look a little worse, not better:** first-of-day E5 +$3,223 -> +$2,931 (-$292), v1 +$1,550 -> +$1,212.
  Mondays now have Friday's high/low, and fading those lost a little. The newer half drops to about 0 (v1 -0.06R, E5 +0.10R).
- The honest number for lane A is the AFTER row. It is still positive and still unproven (the forward gate decides).
- The trades after the first one each day lose money in $ (-$834 v1, -$561 E5). That is why the ladder now judges first-of-day
  trades and tells us to cap the lane at 1 trade a day if the later ones keep losing (tools/of_ladder.py).
- Small print: later-in-day E5 shows +0.23R but -$561: a few tight-stop winners in R, wide-stop losers in $.

Re-run: `python -X utf8 research/orderflow/monfix/run.py` (reads data/pc_days, writes results.json).
