# Order flow v5, family "delta": delta momentum, divergence at 15m swings, overnight delta bias (pre-registered 2026-11-27, BEFORE any result)

PAPER RESEARCH ONLY. Nothing here changes a bot, a size, an arming or an order; no engine/ file is edited. Code:
`research/orderflow/v5/delta/core.py` + `run.py` (written after this file). Out-of-sample scorer: `oos.py` (frozen variants only).

## What I had seen before writing this (honest)
- v4 (`v4_verdict.md`): V2 "delta divergence at the extreme" (12 x 5m bars) = NO as a lane A filter and NO standalone
  (275/214 trades, PF 0.87/0.88); V5 "delta slope into entry" standalone TOO FEW; V7 first-15-min delta NO. All 0/21.
- Battery OF6 "CVD divergence at new RTH high/low" = TOO FEW. Lane A absorption fade = candidate (+0.49R, 40 trades), E5 entry
  best (ofexec). No number for the 6 rules below has been computed by me. I did not open the other v5 families' RESULT.md.
- Data structure only: ET-day files from 00:00 ET, 5m bars (o h l c vol buy sell ...), Sunday files hold 18:00-24:00.

## Data
The 51 usable real NQ tick-summary days 2026-09-27..2026-11-26 (`data/pc_days/<day>/of/`, >= 50,000 trades, quote-rule sides),
read with `engine/ofsum.read` -> `of_battery.Day` (mod = ET minute of day, delta = buy - sell). Thin files (Sundays) are only
overnight history, never traded. Futures only. Halves = the older / newer half of the 51 usable days (sorted, by day).

## Shared trade engine (all 6 variants)
A signal is decided at the CLOSE of a 5m bar i (time t_i + 300 s) with a direction d (+1 long, -1 short) and a stop price.
- **Entry E5 at the signal close** L = close[i]: a resting limit at L for 5 minutes (bar j = i+1). Filled at L if bar j trades
  >= 1 tick through it (long: low[j] <= L - 1 tick; short: high[j] >= L + 1 tick). Otherwise market at the open of bar j+1
  plus 18 ticks against us (long +18 ticks, short -18 ticks). Bars must be contiguous (5 min apart) and open <= 15:55 ET.
- **Stop** = 1 tick beyond the signal's extreme (defined per variant). Minimum stop distance 8 ticks from the fill: if the
  extreme is closer, the stop is set at fill -/+ 8 ticks. Size follows the stop (R = $ / (stop distance x $2/pt)).
  Stop fill = stop - 2 ticks slip (if a bar opens beyond the stop: its open - 2 ticks). A bar that can hit both stop and
  target counts the stop first. On the limit-fill bar j only the stop is checked (fill time inside the bar is unknown).
- **Target** = one target at fill + d x RR x risk, needs 1 tick through. RR per variant.
- **Time exit** at the close of bar i + H (H per variant) - 2 ticks slip; always flat by the 15:50 bar close (- 2 ticks).
- Costs: $1.90 per round turn per micro (MNQ, $0.50 a tick). $ at 1 micro; "$500" = size follows the stop
  (floor(500 / risk$), 1..40 micros), shown as information.
- Book = labelled pool rows (below), one position at a time per variant (a new signal while in a trade is skipped).

## The three ideas, two variants each (6, fixed)
Every variant has a POOL (a price-only condition) and a LABEL (the order-flow read). Every pool row is simulated as if taken;
the BOOK trades only labelled rows. The placebo asks: does the delta label separate winners from losers inside the price pool?

### M = delta burst continuation (5m)
- z_i = (delta_i - mean(delta of bars i-20..i-1)) / sd(same, ddof 1); needs 20 contiguous prior bars in the same day file.
- Signal bars open 10:00-15:00 ET (mod 600..900), bar has >= 20 trades.
- POOL (price confirmation): long if close[i] > max(high[i-3..i-1]); short if close[i] < min(low[i-3..i-1]).
- LABEL: z_i x d >= Z (an aggressive delta burst in the breakout's direction).
- Trade continuation d. Stop = 1 tick beyond the signal bar's opposite extreme (long: low[i] - 1 tick). RR 1.5, H = 6 (30 min).
- **M1**: Z = 2.0. **M2**: Z = 3.0.

### V = delta divergence at 15m swing highs / lows (fade)
- 15m bars = RTH 5m bars grouped from 09:30 (09:30, 09:45, ... complete 3-bar groups only). CVD = cumulative delta from 09:30.
- Pivot high at 15m bar m: high[m] > high[m-1] and high[m] > high[m+1] (known at the close of m+1). Pivot low mirrored.
- POOL (short side): 15m bar q, starting after the close of m+1 of the most recent confirmed pivot high P, is the FIRST 15m bar
  whose high > high[P] (one row per pivot). Signal at q's close (its last 5m bar = i), q closes 10:15..15:00 ET. Long mirrored
  with pivot lows.
- LABEL (divergence): short: CVD at q's close <= CVD at P's close; long: CVD at q's close >= CVD at P's close.
- Trade the fade (d = -1 at a higher high, +1 at a lower low). Stop = 1 tick beyond q's extreme (the new high / low).
  RR 2.0, H = 12 (60 min).
- **V1**: pool as above. **V2**: pool also needs q to CLOSE back inside (short: close[q] < high[P]; long: close[q] > low[P]).

### O = overnight cumulative delta -> RTH open direction
- ON delta = sum of delta of the bars from 18:00 ET of the previous calendar day's file (Monday: the Sunday file) to 09:25 bar
  inclusive (to 09:30); if the previous file is missing, from 00:00 ET of the day file. Needs ON volume >= 20,000.
- Signal at the close of the 09:30 bar (i = the 09:30 bar). Stop = 1 tick beyond the 09:30 bar's extreme against d
  (long: its low - 1 tick). RR 2.0; time exit at the close of the 10:25 bar (H = 11, i.e. 10:30 ET).
- **O1** (price-confirmed): POOL = days whose 09:30 bar closes up (d = +1) or down (d = -1) (close == open: no row).
  LABEL: sign(ON delta) == d. Placebo = label shuffle across days.
- **O2** (pure bias): d = sign(ON delta) every day (ON delta 0: no trade). POOL = both directions simulated every day;
  LABEL = the ON-delta direction. Placebo = the ON-delta sign flipped at random per day (5,000 draws), one-sided on mean R.
  gap = mean R (ON direction) - mean R (opposite direction).

## Scores (fixed now)
Per variant: pool rows, labelled, trades (book), trades/week (= trades / (RTH days / 5)), win %, mean R, PF ($), net $ at
1 micro, max DD ($, by exit time), $ at $500 risk, both halves (book mean R + gap R), gap R (labelled - unlabelled mean R over
the resolved pool), label-shuffle placebo p (one-sided, 5,000 shuffles, seed 7; O2 sign flip as above), Holm over the 6.
- **YES-candidate**: >= 20 trades, net $ > 0, PF >= 1.20, book mean R > 0 AND gap R > 0 in BOTH halves, placebo p < 0.10,
  Holm p < 0.10.
- **weak**: net $ > 0, gap R > 0, placebo p < 0.20 (not all of the above). **NO**: otherwise. **TOO FEW**: < 20 trades.
- A YES is only a reason to freeze and forward-test; strategy rules (both 2026 halves + 2021-25) cannot be met with ticks from
  2026-09 on. Freeze: the best 1-2 variants by (verdict, Holm p, net $) into `frozen.json`, whatever their verdict.
- No look 2. Nothing outside these 6 is scored or reported as a result.
