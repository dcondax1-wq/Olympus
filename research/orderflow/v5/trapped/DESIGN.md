# Order flow v5, family "trapped": trapped-trader fades and initiative continuations (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Code (written after
this file): `research/orderflow/v5/trapped/core.py` (rules; reuses the v5 "levels" simulator `research/orderflow/v5/levels/core.py`
for data loading, the E5 fill, exits, costs, placebo and Holm), `run.py` (in-sample, the 51 days), `oos.py` (frozen variants on
days NOT in the 51).

Question: **when a key level breaks on a 5m close with heavy aggressive delta, does the order flow tell us anything?**
(a) TRAPPED: the break fails back inside within N bars -> the aggressors are trapped -> fade toward the other side.
(b) INITIATIVE: the break holds (the next bar also closes beyond) -> continuation with the breakout.

## What I had seen before writing this (honest)
- Lane A (one-bar rejection of PD / Globex / ORB H/L, ABSORBED = passive side won at the extreme): 40 taken +0.49R, p 0.0065,
  halves differ; E5 entry keeps it YES (real_verdict.md, lanea-proof, ofexec). v4 features 0/21 (V5 delta slope p 0.04 raw only).
  Sibling v5 "levels" RESULT (I read it as part of learning the simulator): absorption at other level types = NO; the simulator
  reproduces lane A (V0 control 63 trades +0.30R one-at-a-time).
- Before writing the thresholds below I looked ONLY at feature distributions, no outcomes: RTH 5m bars (51 days, 3,396 bars)
  |delta| / volume percentiles 50/70/80/90 = 3.3% / 5.2% / 6.6% / 8.8%; bar volume median 5,238 contracts.
- No number for breakout-close + delta, failed-breakout or held-breakout outcomes has been computed by me (or, as far as the repo
  shows, anyone): lane A never takes a bar that CLOSES beyond its level.

## Data
The 51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, meta rows >= 50,000, quote-rule
sides). Thin files (Sundays) are only level history. Bars = `NQ_bars5m` (delta = buy - sell), footprint = `NQ_fp5m`.

## Levels
- **KEY** (lane A's set, `of_battery.levels` via levels/core.v0_levels): pdh, pdl (previous usable day's RTH H/L, within 4
  calendar days), onh, onl (Globex 18:00 previous file .. 09:30), plus orh, orl = 09:30-10:00 range (6 bars), usable for
  breakout bars opening >= 10:00. Two-sided: any key level can be broken either way.
- **SX** session extreme: the RTH high (low) so far = max high (min low) of RTH bars 09:30 .. B-1, for breakout bars B opening
  >= 10:00. Cool-down: after a candidate on one side, the next SX breakout on that side must be >= 6 bars after the previous
  candidate's breakout bar.

## Breakout bar B (signal source)
B opens 09:30-15:00 ET (mod 570..900). Up-break of L: close[B-1] <= L and close[B] > L (KEY); for SX: close[B] > the RTH high
before B. Down-break mirrored. dir = +1 up / -1 down. KEY: one breakout per level per day (the first close beyond uses the
level up, whatever the delta). If several KEY levels break on the same bar, the one nearest the close wins (tie: the list
order pdh, pdl, onh, onl, orh, orl) and all broken levels are used up.

## The order-flow label (the thing the placebo tests)
- **BD** breakout-bar delta: n[B] >= 20 trades and delta[B] x dir >= 0.08 x volume[B] (about the top 12% of RTH bars).
- **XD** beyond-level delta: footprint cells of bars B..F (F = the decision bar) at prices strictly beyond L (>= L + 1 tick for
  an up-break, <= L - 1 tick down): vx = their volume, dx = buy - sell; label = vx >= 100 and dx x dir >= 0.15 x vx
  ("the volume that traded beyond the level was aggressive in the breakout direction").

## The patterns
- **FADE** (trapped): F = the first bar in B+1..B+2 that closes back inside (close[F] < L for an up-break, > L down).
  Trade d = -dir, decision at F's close, entry level = L, stop = 1 tick beyond the excursion extreme (max high of B..F + 1
  tick for an up-break; min low - 1 tick down). No close back inside within 2 bars -> no fade candidate.
- **HOLD** (initiative): F = B+1 and close[B+1] still beyond L (> L up, < L down). Trade d = +dir, decision at F's close,
  entry level = L (the retest), stop = 1 tick beyond the other side of B..F (min low of B..F - 1 tick for an up-break; max
  high + 1 tick down). F must close beyond, else no hold candidate.
- Decision bar F must open 09:45-15:00 ET (mod 585..900).

## Variants (6, fixed; each its own book, one position at a time; BOOK = candidates with label True)
| id | pattern | levels | label |
|---|---|---|---|
| T1 | FADE | KEY | BD |
| T2 | FADE | KEY | XD |
| T3 | FADE | SX | BD |
| C1 | HOLD | KEY | BD |
| C2 | HOLD | KEY | XD |
| C3 | HOLD | SX | BD |
Information only (not scored, no Holm): each variant's price-only book (every candidate, label ignored).

## Trade (identical to v5 levels, `levels/core.simulate`; every candidate simulated "as if taken")
- Entry E5 on 5m bars: decision at F's close; entry bar = F+1. (a) F+1 opens at/beyond L our way -> fill at its open;
  (b) else F+1 trades >= 1 tick through L -> fill at L (on that bar only the stop is checked); (c) else the stop traded in
  F+1 -> no fill; (d) else market at F+2's open + 18 ticks against us. Fill at/beyond the stop -> no trade.
- Stop as above, size follows the stop; stop fill 2 ticks worse (gap open beyond the stop: open - 2 ticks).
- One target at 2R from the fill, needs 1 tick through, fills at the target. Stop first when a bar touches both.
- Flat at the close of the 15:55 bar - 2 ticks. Costs $1.90 a micro round turn. $ at 1 micro MNQ. R = net $ / (risk x $2).
- Busy: a candidate whose decision time (F open + 300 s) is <= the open time of the booked trade's exit bar is not booked.

## Scores (per variant)
trades (booked), trades/week (n / (51/5)), win %, mean R, PF ($), net $ at 1 micro, max DD $, both halves by day (older 26 /
newer 25): booked mean R and label-minus-not gap in R. **Placebo:** label shuffle over every resolved candidate: stat = mean
R(label) - mean R(no label), one-sided, 5,000 shuffles, p = (hits + 1) / 5,001. **Holm-Bonferroni over the 6 placebo p.**

## Pass bar (fixed now; same as v5 levels)
- **YES-candidate**: booked >= 20, net $ > 0, PF >= 1.20, booked mean R > 0 in BOTH halves, gap > 0 in BOTH halves, placebo
  p < 0.10 AND Holm p < 0.10.
- **weak**: booked >= 20, net $ > 0, gap > 0 overall, raw p < 0.20, fails another YES test.
- **TOO FEW**: booked < 20. **NO**: everything else. Trades/week vs the house 2-4/week is reported (information).

## Freeze and out-of-sample
After the run: `frozen.json` = the exact rules of the best 1-2 variants by (verdict, Holm p, net $), even if weak, with the 51
day names. `oos.py` scores ONLY the frozen variants on usable pc_days days NOT in that list, same table, Holm over the frozen
ones. No rule change after this file; a change is a new dated design. The 2021-25 check cannot be run (no ticks before 2026).
