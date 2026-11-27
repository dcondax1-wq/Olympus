# Order flow v5, family "profile": volume-profile setups read with order flow (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Script:
`research/orderflow/v5/profile/run.py` (written after this file), rules in `core.py`. Out-of-sample scorer: `oos.py`.

## What I had seen before writing this (honest)
- Lane A (prior-day H/L, Globex H/L, OR H/L, absorption gate): candidate (real_verdict.md, ofexec: E5 keeps it YES).
- v5 "levels" (sibling): Globex VAH/VAL/POC + absorption = NO (-$652), naked prior-day POCs = 3 candidates in 51 days, VWAP
  bands / round numbers = NO. OF3A (LVN rejection, first of the day, prior RTH 2-pt bins) = TOO FEW in the battery.
- No number for the 6 variants below (80% rule, prior-RTH VA edges, composite LVNs, POC magnet) has been computed by me or,
  as far as the repo shows, by anyone on these days.

## Data
The 51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, >= 50,000 trades, quote-rule sides;
files are ET calendar days). Only bars with an RTH session that day can trade (Sundays / closed days give no candidate).
Thin files are loaded as profile history only.

## Profiles (footprint-built, `of_battery.Day` cells: price = bar low + k ticks, volume = a + b + u)
- **Prior RTH day** = the latest earlier file (within 4 calendar days) with >= 40 RTH bars (09:30-16:00 ET opens).
- **Prior RTH profile**: every footprint cell of that day's RTH bars, summed into 1-point bins (bin = floor(price)).
  POC = max-volume bin (tie: lower), POC price = bin + 0.50. Value area (70%): start at the POC bin, add the adjacent bin
  (above or below) with more volume (tie: above) until >= 70% of the volume. VAH = top VA bin + 0.75, VAL = lowest VA bin.
  (Same `profile()` as v5 levels.) Levels rounded to the tick.
- **Overnight profile**: previous calendar day file bars opening >= 18:00 ET + today's bars opening < 09:30 ET.
- **Composite** (LVN only) = prior RTH cells + overnight cells. Smoothed volume s = centered 5-bin moving average (edges: mean
  of the bins available). LVN bin j: s[j] = min of s over [j-5, j+5], s[j] <= 0.35 x max(s), and max(s[j+3 .. j+30]) >= 2 x s[j]
  and max(s[j-30 .. j-3]) >= 2 x s[j] (both sides exist in range). LVN price = bin + 0.50. Two LVNs < 6 bins apart: keep the
  lower s (tie: lower price).

## Order-flow reads (all from the summary: bar delta = buy - sell; zone = of_battery.Day.zone, OF1 constants)
- ABSORBED (P3, P6) = lane A / OF1: zone within 8 ticks of the signal bar's pushed extreme, vz > 0, dz x d < 0,
  |dz| >= 0.20 x vz, bar >= 20 trades.
- DELTA-WITH (P4) = signal bar delta x d > 0 and |delta| >= 0.10 x bar volume.
- WINDOW-DELTA (P1, P2, P5) = sum of bar delta over the stated window x d > 0.
Each variant's GATE is its read. Every candidate is simulated as if taken; the BOOK = gated candidates, one position at a time.

## Variants (6, fixed)
| id | setup | signal | d | level for E5 | stop (1 tick beyond) | target (one) | gate |
|---|---|---|---|---|---|---|---|
| P1 | 80% rule, classic | RTH open (09:30 bar open) > prior VAH (short) or < prior VAL (long); 30-min periods from 09:30; the first time two consecutive periods CLOSE inside (VAL < close < VAH, close of the period's last 5m bar); 2nd period must start <= 12:30. Signal bar = the 2nd period's last bar | toward the far edge | the re-entered edge (VAH short / VAL long) | extreme of the 12 bars of the 2 periods (high for short) | far VA edge (VAL for short / VAH for long) | WINDOW-DELTA over those 12 bars |
| P2 | 80% rule, fast | open outside as P1; the first time two consecutive 5m bars close inside the VA, 2nd bar opening 09:35-12:00 | as P1 | as P1 | extreme of the 2 bars | as P1 | WINDOW-DELTA over the 2 bars |
| P3 | prior-RTH VA edge fade | bar opening 09:45-15:00: high >= VAH + 1 tick and close < VAH (short) / low <= VAL - 1 tick and close > VAL (long); one per edge per day | fade | the edge | signal bar extreme | 2R | ABSORBED |
| P4 | composite LVN rejection | bar opening 09:45-15:00 rejects an LVN L: open > L, low <= L - 1 tick, close > L (long) / open < L, high >= L + 1 tick, close < L (short); one per LVN per day; several on one bar: nearest the pushed extreme | rejection | L | signal bar extreme | 2R | DELTA-WITH |
| P5 | POC magnet, inside-value open | RTH open inside the prior VA (VAL < open < VAH); 09:40 bar close c on the same side of the prior POC as the open, |c - POC| >= max(8 pts, 0.25 x (VAH - VAL)). Signal bar = 09:40 bar | toward the POC | none (market) | the 09:30-09:45 extreme on the far side (low for a long) | prior POC | WINDOW-DELTA over 09:30-09:45 (3 bars) |
| P6 | prior-RTH VA edge fade to POC | P3's candidates exactly | fade | the edge | as P3 | prior POC | ABSORBED |
For P1/P2: no candidate if any RTH bar up to the signal bar already traded the far edge (traverse done). For P6 / P1 / P2 / P5:
if the fill is at/beyond the target -> "no room", no trade (P3/P4: target is 2R from the fill).

## Trade (common; the v5 levels simulator with a target price parameter)
- Entry E5 (coarse, 5m): decision at the signal bar close; entry bar = the next bar. With a level L: (a) entry bar opens
  at/beyond L our way (short: open >= L) -> fill at its open; (b) else the entry bar trades >= 1 tick through L -> fill at L
  (on that bar only the stop is checked); (c) else the stop traded in the entry bar -> no fill; (d) else market at the next
  bar's open + 18 ticks against us. Without a level (P5): market at the entry bar's open + 18 ticks against us.
  Fill at/beyond the stop -> no trade. Entry bars must open <= 15:55.
- Exits on closed 5m bars; stop first when a bar touches both; stop fill 2 ticks worse (gap open beyond the stop: open - 2
  ticks); the target needs 1 tick through and fills at the target; flat at the close of the 15:55 bar - 2 ticks.
- Costs: $1.90 a micro round turn. $ at 1 micro MNQ ($0.50 a tick). R = net $ / (risk x $2) (costs in R). Size follows the stop
  ($500-risk size shown as info: micros = 500 // (risk x $2), 1..40).
- Busy: a candidate whose decision time (signal bar open + 300 s) is <= the open time of the booked trade's exit bar is busy.

## Scores (per variant; the v5 levels `score()`)
trades (booked), trades/week (n / (51/5)), win %, mean R, PF ($), net $ at 1 micro, max DD $, both halves by day (older 26 /
newer 25 usable days): booked mean R and gated-minus-not gap in R. Also (info, not scored) every candidate ungated.
**Placebo:** gate-label shuffle over every resolved candidate: stat = mean R(gated) - mean R(not gated), one-sided, 5,000
shuffles, p = (hits + 1) / 5,001. **Holm-Bonferroni over the 6 variants' placebo p.**

## Pass bar (fixed now; same as the sibling families)
- **YES-candidate**: booked >= 20, net $ > 0, PF >= 1.20, booked mean R > 0 in BOTH halves, gap > 0 in BOTH halves,
  placebo p < 0.10 AND Holm p < 0.10.
- **weak**: booked >= 20, net $ > 0, gap > 0, raw p < 0.20, fails another YES test. **TOO FEW**: booked < 20. **NO**: the rest.
- House 2-4 trades/week reported, not a gate.

## Freeze and out-of-sample
After the run: `frozen.json` = the exact rules of the best 1-2 variants by (verdict rank, Holm p, net $), even if weak, with the
51 in-sample day names. `oos.py` scores only the frozen variants on pc_days days NOT in that list (in-sample days may serve as
profile history, never as traded days) and prints the same table (Holm over the frozen ones). No rule changes after this file.
The 2021-25 check cannot be run (no ticks before 2026).
