# Order flow v5, family "exhaustion": exhaustion prints, finished / unfinished auctions, delta exhaustion (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Code:
`research/orderflow/v5/exhaustion/core.py` + `run.py` (written after this file). Out-of-sample scorer: `oos.py` (frozen rules only).

## What I had seen before writing this (honest)
- Prior work: lane A absorption fade at levels = candidate (real_verdict, ofexec E5); v4 V2 "delta divergence at the extreme"
  (filter on lane A + standalone 30-min) = NO; v5 levels = NO; hq-reversion (day-range "exhaustion" fades on bars) = NO;
  TD Sequential 9-count exhaustion = NO. No footprint exhaustion print / finished-auction / push-delta-exhaustion test exists.
- I peeked at FEATURE DISTRIBUTIONS ONLY (no outcome, no R, no price after the signal bar) to avoid empty variants:
  push pool below = 283 bars (27.7 / week); thin-top ratio <= 0.33 in 30% of them; a zero aggressive print on the single extreme
  tick in 1% (so the single-tick "finished auction" would be empty: I use the 1-point row instead); top 1-point row two-sided
  (unfinished) 73%; push with all 3 deltas our way 42%, delta fade <= 0.33 in 23% of the pool.

## Data
51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, >= 50,000 trades, quote-rule sides).
Footprint per 5m bar: k = ticks above the bar low, a = ask (buy aggressor) volume, b = bid (sell aggressor), u = unknown.
Loader: `research/orderflow/v5/levels/core.py` load_days (of_battery.Day).

## The pool (shared by X1-X5; X6 uses it plus a room rule)
Signal bar i = a closed 5m bar opening 09:45-15:00 ET (mod 585..900), >= 20 trades, footprint present, and the 12 bars before it
contiguous (t[i] - t[i-12] = 3600 s).
- UP push (s = +1): bars i-3, i-2, i-1 all close > open, and high[i] > max(high[i-12..i-1]) (a new 1-hour high).
- DOWN push (s = -1): bars i-3, i-2, i-1 all close < open, and low[i] < min(low[i-12..i-1]).
"Extreme" = the high for s = +1, the low for s = -1. "Aggressive side" = ask volume for s = +1, bid volume for s = -1
(the side pushing into the extreme); "passive side" = the other one. Distance from the extreme in ticks: kk = kmax - k (up)
or k (down), kmax = (high - low) / tick.

## Labels (each computed from bar i and earlier only)
- **THIN** (exhaustion print): bar range >= 24 ticks; A8 = aggressive volume in kk 0..7 / 8, A16 = aggressive volume in kk 8..23
  / 16; THIN = A16 > 0 and A8 <= 0.33 x A16 (aggression dries up into the extreme).
- **FIN** (finished auction, 1-point row): the top row = kk 0..3; FIN = aggressive volume in it = 0 OR passive volume in it = 0
  (one-sided top row). UNF (unfinished) = both > 0.
- **DEX** (delta exhaustion after 3 same-direction bars): delta x s > 0 on each of bars i-3, i-2, i-1 (delta = buy - sell),
  and delta[i] x s <= 0.33 x mean(delta[i-3..i-1] x s) (includes a flipped delta).

## Variants (6, fixed; each its own book, one position at a time)
| id | trade | label (booked when true) |
|---|---|---|
| X1 | fade (d = -s) | THIN |
| X2 | fade | FIN |
| X3 | fade | DEX |
| X4 | fade | THIN and DEX |
| X5 | fade | at least 2 of THIN, FIN, DEX |
| X6 | revisit, WITH the push (d = +s) | UNF, on pool bars whose close is >= 40 ticks (10 pts) from the extreme |

## Trade (every pool candidate is simulated "as if taken"; the BOOK = labelled candidates, one position at a time)
- Decision at bar i's close. No level exists here, so entry = MARKET at the open of bar i+1 + 18 ticks against us
  (the house E5 fallback / today's 2.75 s delay). Bar i+1 must exist, be contiguous and open <= 15:55.
- Stop = 1 tick beyond bar i's extreme on the side that would prove us wrong: fades -> 1 tick beyond the exhaustion extreme
  (high + 1 tick for a short, low - 1 tick for a long); X6 -> 1 tick beyond bar i's opposite extreme (low - 1 tick for an up
  push). Size follows the stop. Fill at/beyond the stop -> no trade.
- Target: fades X1-X5 = one target at 2R from the fill (lane A's), needs 1 tick through, fills at the target.
  X6 = the unfinished extreme itself (the revisit), needs 1 tick through, fills at the extreme; if the fill is < 8 ticks from
  it -> no trade ("no room").
- Exits on closed 5m bars from bar i+1 (entry bar included), stop first when a bar touches both; stop fill 2 ticks worse (gap
  open beyond the stop: open - 2 ticks); flat at the close of the 15:55 bar - 2 ticks.
- Costs $1.90 a micro round turn. $ at 1 micro MNQ ($2 a point). R = net $ / (risk x $2) (costs in R).
- Busy: a candidate whose decision time (bar i open + 300 s) is <= the open time of the booked trade's exit bar is not booked.
  No-fill / no-room rows never block.
- Sensitivity (information only, not in any verdict): the same books with entry at bar i+1 open + 1 tick.

## Scores (per variant)
trades (booked), trades/week (n / (51 / 5)), win %, mean R, PF ($), net $ at 1 micro, max DD $ (booked, by exit time),
$ at $500 risk (info), both halves by day (older 26 / newer 25): booked mean R and the labelled-minus-unlabelled gap in R.
**Placebo:** label shuffle over every resolved candidate of that variant's pool (as if taken): stat = mean R(label) - mean
R(no label), one-sided, 5,000 shuffles, p = (hits + 1) / 5,001. **Holm-Bonferroni over the 6 variants' placebo p.**
Also printed (info): the pool as if all taken (does the push-extreme fade / revisit itself make money).

## Pass bar (fixed now; same as v5 levels)
- **YES-candidate**: booked >= 20, net $ > 0, PF >= 1.20, booked mean R > 0 in BOTH halves, gap > 0 in BOTH halves, placebo
  p < 0.10 AND Holm-adjusted p < 0.10.
- **weak**: booked >= 20, net $ > 0, gap > 0 overall, raw p < 0.20, but fails another YES test.
- **TOO FEW**: booked < 20. **NO**: everything else. Trades/week reported against the house 2-4 / week (information).

## Freeze and out-of-sample
After the run: `frozen.json` = the exact rules of the best 1-2 variants by (verdict rank, Holm p, net $) even if weak, with the
51 day names. `oos.py` scores ONLY the frozen variants on pc_days days NOT in that list (>= 50,000 trades) and prints the same
table (Holm over the frozen ones). No rule changes after this file; a change is a new dated design. The 2021-25 test cannot be
run (no ticks before 2026); nothing goes near a bot without the OOS pass and the owner's yes.
