# Order flow v5, family "sessions": lane A by session window, and first-touch vs any-touch (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Code (written after
this file): `research/orderflow/v5/sessions/core.py` (rules), `run.py` (in-sample, the 51 days), `oos.py` (frozen variants on days
NOT in the 51). Question: **is lane A's absorbed-level-fade edge concentrated in one session window, and does "first touch only"
beat "any touch"?**

## What I had seen before writing this (honest)
- Lane A (09:45-15:00, PD H/L, Globex H/L, ORB H/L): 40 taken +0.49R, skipped -0.31R, p 0.0065, halves differ (real_verdict.md);
  E5 entry keeps it YES (ofexec). lanea-proof's descriptive time split of the TAKEN trades: 09:45-10:30 32 trades +0.40R,
  10:30-12:00 7 trades +1.14R, 12:00-15:00 1 trade -1.02R. So I already know NY open holds most of lane A's trades and that
  lane A barely trades after noon. Nothing about London (02:00-05:00), about 09:30-09:45, about levels re-armed per window, or
  about first-touch / any-touch has been computed by me or (as far as the repo shows) anyone.
- I have NOT looked at the sibling v5 families' results (levels, targets).

## Data
The 51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, meta rows >= 50,000, quote-rule sides).
Each file = one ET calendar day 00:00-24:00 of 5m bars + footprint. Thin files (Sundays) are used only as level history (the
Sunday 18:00 open feeds Monday's Asia / Globex range), never traded.

## Levels (all known at the bar's open; one-sided as lane A: a HIGH-type level is faded SHORT, a LOW-type level LONG)
- **pdh / pdl**: previous usable day's RTH (09:30-16:00) high / low, previous usable day within 4 calendar days (of_battery.levels).
- **onh / onl** (NY windows): Globex high / low = previous calendar-day file bars from 18:00 + today's bars before 09:30.
- **orh / orl** (NY windows, from 10:00): the 09:30-10:00 range (6 bars).
- **ash / asl** (London window): Asia high / low = previous calendar-day file bars from 18:00 + today's bars before 02:00.
| window | signal-bar opens (ET) | level set | flat at the close of the bar opening |
|---|---|---|---|
| LON London | 02:00-04:55 | pdh pdl ash asl | 09:25 (out before the NY open) |
| NYO NY open | 09:30-10:25 | pdh pdl onh onl orh orl | 15:55 |
| MID NY midday | 10:30-13:25 | pdh pdl onh onl orh orl | 15:55 |
| PM NY afternoon | 13:30-15:25 | pdh pdl onh onl orh orl | 15:55 |

## The signal (lane A's rule)
A closed 5m bar REJECTS a high-type level L when high >= L + 1 tick and close < L (-> short, d = -1); a low-type level when
low <= L - 1 tick and close > L (-> long, d = +1). Several levels rejected by one bar -> ONE candidate: the first in the order
pdh, pdl, onh, onl, orh, orl, ash, asl; the others count as used/touched.
Touch modes:
- **WIN (per-window first rejection)**: each level gives at most one candidate per window: the first rejecting bar inside the
  window (levels re-arm at each window start). This is lane A's "one signal per level per day" applied per window.
- **FT (first touch only)**: a level can give a candidate only on its FIRST TOUCH since it became known (touch = high >= L for a
  high-type, low <= L for a low-type). Known from: pdh/pdl the previous usable day's 16:00 bar (that file's bars >= 16:00 and every
  bar since, both files when consecutive), onh/onl 09:30, orh/orl 10:00, ash/asl 02:00. If that first touch is not a rejection, or
  falls outside the variant's windows, the level is dead for the day.
- **ANY (any touch)**: every rejecting bar inside the windows is a candidate (a level can fire many times a day).

## The absorption gate (unchanged OF1 / of_paper lane A constants)
Zone = footprint prices within 8 ticks of the signal bar's extreme on the push side (`of_battery.Day.zone`); vz = zone volume,
dz = zone buy - sell. ABSORBED = vz > 0 and dz x d < 0 and |dz| >= 0.20 x vz (bar must have >= 20 trades). Only absorbed
candidates are booked; every candidate is simulated "as if taken" for the placebo.

## Trade (as v5 levels' coarse E5 on the 5m summary, so in-sample and the new OOS days use the same simulator)
- Stop = 1 tick beyond the signal bar's extreme. Size follows the stop (R = $ / (risk x $2)).
- Entry E5: decision at the signal bar close, entry bar = the next bar. (a) entry bar opens at/beyond L our way -> fill at its
  open; (b) else the entry bar trades >= 1 tick through L -> fill at L (that bar checks only the stop); (c) else the stop traded
  in it -> no trade; (d) else market at the following bar's open + 18 ticks against us. Risk <= 0 -> no trade. The entry bar must
  be the next 5m bar and open at or before the window's flat bar.
- One target 2R from the fill (lane A), needs 1 tick through, fills at the target. Stop first when one bar touches both; stop fill
  2 ticks worse (gap through: that open - 2 ticks). Flat at the close of the window's flat bar - 2 ticks.
- Costs $1.90 a micro round turn, in R and $. $ at 1 micro MNQ ($0.50 a tick).
- BOOK = absorbed, resolved candidates, one position at a time per variant: a candidate whose decision time (bar open + 300 s) is
  <= the booked trade's exit bar open is busy (not booked).

## Variants (6, fixed)
| id | windows | touch mode |
|---|---|---|
| S1 | LON | WIN |
| S2 | NYO | WIN |
| S3 | MID | WIN |
| S4 | PM | WIN |
| S5 | LON + NYO + MID + PM | FT |
| S6 | LON + NYO + MID + PM | ANY |
Descriptive (not tested, not frozen, not in Holm): V0 = lane A exactly (09:45-15:00 one-per-day, its levels) through this
simulator as a check; S5 / S6 split by window; S1-S4 pooled ("WIN all windows").

## Scores (per variant)
candidates, absorbed, trades (booked), trades/week (= n / (51 / 5)), win %, mean R, PF ($), net $ at 1 micro, $ at $500 risk
(micros = 500 // (risk x 2), 1..40), max DD $ (booked, by exit time), both halves by day (older 26 / newer 25): booked n, mean R,
$, and the absorbed-minus-not gap in R.
**Placebo**: label shuffle over every resolved candidate: stat = mean R(absorbed) - mean R(not absorbed), one-sided, 5,000
shuffles (seed 7), p = (hits + 1) / 5,001. **Holm-Bonferroni over the 6 variants' placebo p.**

## Pass bar (fixed now)
- **YES-candidate**: booked >= 20, net $ > 0, PF >= 1.20, booked mean R > 0 in BOTH halves, gap > 0 in BOTH halves, placebo
  p < 0.10 AND Holm p < 0.10.
- **weak**: booked >= 20, net $ > 0, gap > 0, raw p < 0.20, fails another YES test. **TOO FEW**: booked < 20. **NO**: the rest.
- "Concentrated in one window" = exactly one of S1-S4 is YES-candidate or weak while the other three are NO / TOO FEW with
  booked mean R <= 0 or n < 10. Trades/week vs the house 2-4 is reported, not a gate.

## Freeze and out-of-sample
After the run `frozen.json` = the best 1-2 tested variants by (verdict YES > weak > NO > TOO FEW, then Holm p, then net $), even if
weak; the 51 day names are listed in it. `oos.py` scores ONLY the frozen variants on usable pc_days NOT in that list, same table,
Holm over the frozen ones, halves = the OOS days split by date. Levels may use in-sample days as history only. No rule changes
after this file; a change is a new dated design. Nothing goes near a bot without the OOS / forward pass and the owner's yes.
