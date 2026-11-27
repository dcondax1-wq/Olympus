# Order flow v5, family "levels": lane A's absorption fade at MORE level types (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Script:
`research/orderflow/v5/levels/run.py` (written after this file). Out-of-sample scorer: `oos.py` (same rules, frozen variants only).

## What I had seen before writing this (honest)
- Lane A on its own levels (prior-day RTH H/L, Globex H/L, opening-range H/L): 40 taken +0.49R, skipped -0.31R, p 0.0065,
  halves differ (real_verdict.md, lanea-proof); E5 entry keeps it YES (ofexec). Splits: Globex/ORB good, prior-day weak (n=6).
- v4: 0/21 features. No number for any of the level types below has been computed by me or (as far as the repo shows) anyone.

## Data
The 51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, >= 50,000 trades, quote-rule sides).
Thin days (Sundays, half days) are loaded only as level history (Globex profile / naked-POC check), never traded.
Prior-week H/L come from `data/NQ_5m.csv` (futures, NinjaTrader/TradingView NQ continuous) shifted onto the tick prices by the
day's median (tick-summary open - NQ_5m open) over matching bars (handles back-adjusted rolls; 0.0 on these days).

## The absorption read (unchanged from of_paper lane A / OF1)
Signal bar = a closed 5m bar. d = fade direction. Zone = footprint prices within 8 ticks of the bar's extreme on the push side
(the low for a long, the high for a short) via `of_battery.Day.zone`; vz = zone volume, dz = zone buy - sell.
ABSORBED = vz > 0 and dz x d < 0 and |dz| >= 0.20 x vz (bar must have >= 20 trades, else not absorbed).

## The level rule (one rule for every new level type: a two-sided rejection)
Bars opening 09:45-15:00 ET (mod 585..900). For a level price L known at the bar's open:
- from above: bar open > L, bar low <= L - 1 tick, bar close > L  -> LONG (d = +1)
- from below: bar open < L, bar high >= L + 1 tick, bar close < L -> SHORT (d = -1)
One candidate per level per day (the first bar that fires uses the level up, absorbed or not, as lane A). At most ONE candidate
per bar per variant: when several levels fire on the same bar, the one in the fixed priority order below wins (within one type:
the level nearest the bar's pushed extreme); all fired levels are used up.

## Level types (all built only from data before the bar that can trade them)
- **PW** prior-week high / low: the full CME week before the current one (previous Sunday 18:00 ET .. previous Friday 17:00 ET).
  If NQ_5m.csv has < 20 bars matching the day (e.g. days after it ends), the prior week's pc_days files are used instead
  (needs >= 4 of its 5 weekday files); else no PW level that day.
- **GX** Globex value area from the footprint: profile of every bar from 18:00 ET of the previous calendar day's file (Monday:
  the Sunday file) to 09:30 ET today, volume summed into 1-point bins (bin = floor(price)). POC = max-volume bin (tie: lower);
  value area = start at the POC bin, add the adjacent bin (above or below) with more volume (tie: above) until >= 70% of the
  volume. Levels: GX-POC = POC bin + 0.50, GX-VAH = top VA bin + 0.75, GX-VAL = lowest VA bin + 0.00. Needs >= 20,000 contracts.
- **NP** naked prior-day POCs: RTH (09:30-16:00) POC (same 1-point method) of each of the last 5 usable trading days; a POC is a
  level today only if no bar from its day's 16:00 to today's 09:30 traded it (low <= POC <= high); a missing calendar day in
  between (no file; Saturdays never have one and are skipped) = unknown -> not used.
- **VW** RTH VWAP +/- 1 sd: anchored 09:30, from footprint price x volume; VWAP and the volume-weighted sd of price are taken at
  the CLOSE OF THE PREVIOUS BAR (known at the signal bar's open). Levels VW+1 and VW-1 (moving; L = the value at that bar).
- **RN** round numbers: every multiple of 50.0 points (00 and 50).

## Variants (6, fixed; each its own book, one position at a time)
| id | levels | priority |
|---|---|---|
| L1 | PW high/low | - |
| L2 | GX POC / VAH / VAL | VAH, VAL, POC |
| L3 | NP naked prior-day POCs (<= 5) | newest first |
| L4 | VW +1 sd / -1 sd | - |
| L5 | RN 00/50 | nearest the extreme |
| L6 | union of L1-L5 | PW, GX, NP, VW, RN |
A control V0 (lane A's own pdh/pdl/onh/onl/orh/orl through THIS simulator) is printed to check the simulator against the
known E5 result. V0 is NOT a variant: not scored, not in Holm, not frozen.

## Trade (every candidate is simulated "as if taken"; the BOOK = absorbed candidates, one position at a time)
- Stop = 1 tick beyond the signal bar's extreme (low - 1 tick for a long, high + 1 tick for a short). Size follows the stop.
- Entry E5 on the 5m summary (DESIGN_paper_v2 coarse): decision at the signal bar close; entry bar = the next bar.
  (a) entry bar opens at/beyond L our way -> fill at its open (marketable); (b) else the entry bar trades >= 1 tick through L
  -> fill at L (on that bar only the stop is checked); (c) else the stop traded in the entry bar -> no fill; (d) else market at
  the following bar's open + 18 ticks against us. Fill at/beyond the stop -> no trade.
- Target = one target at 2R from the fill (lane A's), needs 1 tick through, fills at the target.
- Exits on closed 5m bars, stop first when a bar touches both; stop fill 2 ticks worse (gap open beyond the stop: open - 2
  ticks); flat at the close of the 15:55 bar - 2 ticks.
- Costs: $1.90 a micro round turn. $ at 1 micro MNQ ($0.50 a tick). R = net $ / (risk x $2) (costs in R).
- Busy: a candidate whose decision time (signal bar open + 300 s) is <= the open time of the booked trade's exit bar is "busy"
  (not booked). No-fill rows never block.

## Scores (per variant)
trades (booked), trades/week (= n / (51 days / 5)), win %, mean R, PF ($), net $ at 1 micro, max DD $ (booked, by exit time),
both halves by day (older 26 days / newer 25 days): booked mean R and the absorbed-minus-not gap in R.
**Placebo:** label shuffle over every resolved candidate (as if taken): stat = mean R(absorbed) - mean R(not absorbed),
one-sided, 5,000 shuffles, p = (hits + 1) / (5,001). **Holm-Bonferroni over the 6 variants' placebo p.**

## Pass bar (fixed now)
- **YES-candidate**: booked >= 20, net $ > 0, PF >= 1.20, booked mean R > 0 in BOTH halves, gap > 0 in BOTH halves, placebo
  p < 0.10 AND Holm-adjusted p < 0.10.
- **weak**: booked >= 20, net $ > 0, gap > 0 overall, raw p < 0.20, but fails another YES test.
- **TOO FEW**: booked < 20. **NO**: everything else.
- Trades/week is reported against the house 2-4/week (L5/L6 may run hotter; that is information, not a gate).

## Freeze and out-of-sample
After the run: `frozen.json` = the exact rules of the best 1-2 variants by (verdict, Holm p, net $) even if weak; the 51 day
names are listed in it. `oos.py` scores ONLY the frozen variants on pc_days days NOT in that list, prints the same table (Holm
over the frozen ones). No rule changes after this file; a change is a new dated design. Nothing goes near a bot without the
forward/OOS pass and the owner's yes; the 2021-25 test cannot be run (no ticks before 2026).
